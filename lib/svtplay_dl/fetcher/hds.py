# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import base64
import binascii
import copy
import struct
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.error import UIException
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import output
from svtplay_dl.utils.output import progress_stream
from svtplay_dl.utils.output import progressbar


def _chr(temp):
    return chr(temp)


class HDSException(UIException):
    def __init__(self, url, message):
        self.url = url
        super().__init__(message)


class LiveHDSException(HDSException):
    def __init__(self, url):
        super().__init__(url, "This is a live HDS stream, and they are not supported.")


def hdsparse(config, res, manifest, output=None):
    streams = {}
    bootstrap = {}

    if not res:
        return streams

    if res.status_code >= 400:
        streams[0] = ServiceError(f"Can't read HDS playlist. {res.status_code}")
        return streams
    data = res.text

    xml = ET.XML(data)

    bootstrapIter = xml.iter("{http://ns.adobe.com/f4m/1.0}bootstrapInfo")
    mediaIter = xml.iter("{http://ns.adobe.com/f4m/1.0}media")

    if xml.find("{http://ns.adobe.com/f4m/1.0}drmAdditionalHeader") is not None:
        streams[0] = ServiceError("HDS DRM protected content.")
        return streams
    for i in bootstrapIter:
        if "id" in i.attrib:
            bootstrap[i.attrib["id"]] = i.text
        else:
            bootstrap["0"] = i.text
    parse = urlparse(manifest)
    querystring = parse.query
    url = f"{parse.scheme}://{parse.netloc}{parse.path}"
    for i in mediaIter:
        bootstrapid = bootstrap[i.attrib["bootstrapInfoId"]]
        streams[int(i.attrib["bitrate"])] = HDS(
            copy.copy(config),
            url,
            i.attrib["bitrate"],
            url_id=i.attrib["url"],
            bootstrap=bootstrapid,
            metadata=i.find("{http://ns.adobe.com/f4m/1.0}metadata").text,
            querystring=querystring,
            cookies=res.cookies,
            output=output,
        )
    return streams


class HDS(VideoRetriever):
    @property
    def name(self):
        return "hds"

    def download(self):
        self.output_extention = "flv"
        if self.config.get("live") and not self.config.get("force"):
            raise LiveHDSException(self.url)

        querystring = self.kwargs["querystring"]
        cookies = self.kwargs["cookies"]
        bootstrap = base64.b64decode(self.kwargs["bootstrap"])
        box = readboxtype(bootstrap, 0)
        antal = None
        if box[2] == b"abst":
            antal = readbox(bootstrap, box[0])
        baseurl = self.url[0 : self.url.rfind("/")]

        file_d = output(self.output, self.config, "flv")
        if file_d is None:
            return

        metasize = struct.pack(">L", len(base64.b64decode(self.kwargs["metadata"])))[1:]
        file_d.write(binascii.a2b_hex(b"464c560105000000090000000012"))
        file_d.write(metasize)
        file_d.write(binascii.a2b_hex(b"00000000000000"))
        file_d.write(base64.b64decode(self.kwargs["metadata"]))
        file_d.write(binascii.a2b_hex(b"00000000"))
        i = 1
        start = antal[1]["first"]
        total = antal[1]["total"]
        eta = ETA(total)
        while i <= total:
            url = "{}/{}Seg1-Frag{}?{}".format(baseurl, self.kwargs["url_id"], start, querystring)
            if not self.config.get("silent"):
                eta.update(i)
                progressbar(total, i, "".join(["ETA: ", str(eta)]))
            data = self.http.request("get", url, cookies=cookies)
            if data.status_code == 404:
                break
            data = data.content
            number = decode_f4f(i, data)
            file_d.write(data[number:])
            i += 1
            start += 1

        file_d.close()
        if not self.config.get("silent"):
            progress_stream.write("\n")
        self.finished = True


def readbyte(data, pos):
    return struct.unpack("B", bytes(_chr(data[pos]), "ascii"))[0]


def read16(data, pos):
    endpos = pos + 2
    return struct.unpack(">H", data[pos:endpos])[0]


def read24(data, pos):
    end = pos + 3
    return struct.unpack(">L", "\x00" + data[pos:end])[0]


def read32(data, pos):
    end = pos + 4
    return struct.unpack(">i", data[pos:end])[0]


def readu32(data, pos):
    end = pos + 4
    return struct.unpack(">I", data[pos:end])[0]


def read64(data, pos):
    end = pos + 8
    return struct.unpack(">Q", data[pos:end])[0]


def readstring(data, pos):
    length = 0
    while bytes(_chr(data[pos + length]), "ascii") != b"\x00":
        length += 1
    endpos = pos + length
    string = data[pos:endpos]
    pos += length + 1
    return pos, string


def readboxtype(data, pos):
    boxsize = read32(data, pos)
    tpos = pos + 4
    endpos = tpos + 4
    boxtype = data[tpos:endpos]
    if boxsize > 1:
        boxsize -= 8
        pos += 8
        return pos, boxsize, boxtype


# Note! A lot of variable assignments are commented out. These are
# accessible values that we currently don't use.
def readbox(data, pos):
    # version = readbyte(data, pos)
    pos += 1
    # flags = read24(data, pos)
    pos += 3
    # bootstrapversion = read32(data, pos)
    pos += 4
    # byte = readbyte(data, pos)
    pos += 1
    # profile = (byte & 0xC0) >> 6
    # live = (byte & 0x20) >> 5
    # update = (byte & 0x10) >> 4
    # timescale = read32(data, pos)
    pos += 4
    # currentmediatime = read64(data, pos)
    pos += 8
    # smptetimecodeoffset = read64(data, pos)
    pos += 8
    temp = readstring(data, pos)
    # movieidentifier = temp[1]
    pos = temp[0]
    serverentrycount = readbyte(data, pos)
    pos += 1
    serverentrytable = []
    i = 0
    while i < serverentrycount:
        temp = readstring(data, pos)
        serverentrytable.append(temp[1])
        pos = temp[0]
        i += 1
    qualityentrycount = readbyte(data, pos)
    pos += 1
    qualityentrytable = []
    i = 0
    while i < qualityentrycount:
        temp = readstring(data, pos)
        qualityentrytable.append(temp[1])
        pos = temp[0]
        i += 1

    tmp = readstring(data, pos)
    # drm = tmp[1]
    pos = tmp[0]
    tmp = readstring(data, pos)
    # metadata = tmp[1]
    pos = tmp[0]
    segmentruntable = readbyte(data, pos)
    pos += 1
    if segmentruntable > 0:
        tmp = readboxtype(data, pos)
        boxtype = tmp[2]
        boxsize = tmp[1]
        pos = tmp[0]
        if boxtype == b"asrt":
            antal = readasrtbox(data, pos)
            pos += boxsize
    fragRunTableCount = readbyte(data, pos)
    pos += 1
    i = 0
    first = 1
    while i < fragRunTableCount:
        tmp = readboxtype(data, pos)
        boxtype = tmp[2]
        boxsize = tmp[1]
        pos = tmp[0]
        if boxtype == b"afrt":
            first = readafrtbox(data, pos)
            pos += boxsize
        i += 1
    antal[1]["first"] = first
    return antal


# Note! A lot of variable assignments are commented out. These are
# accessible values that we currently don't use.
def readafrtbox(data, pos):
    # version = readbyte(data, pos)
    pos += 1
    # flags = read24(data, pos)
    pos += 3
    # timescale = read32(data, pos)
    pos += 4
    qualityentry = readbyte(data, pos)
    pos += 1
    i = 0
    while i < qualityentry:
        temp = readstring(data, pos)
        # qualitysegmulti = temp[1]
        pos = temp[0]
        i += 1
    fragrunentrycount = read32(data, pos)
    pos += 4
    i = 0
    first = 1
    skip = False
    while i < fragrunentrycount:
        firstfragment = readu32(data, pos)
        if not skip:
            first = firstfragment
            skip = True
        pos += 4
        # timestamp = read64(data, pos)
        pos += 8
        # duration = read32(data, pos)
        pos += 4
        i += 1
    return first


# Note! A lot of variable assignments are commented out. These are
# accessible values that we currently don't use.
def readasrtbox(data, pos):
    # version = readbyte(data, pos)
    pos += 1
    # flags = read24(data, pos)
    pos += 3
    qualityentrycount = readbyte(data, pos)
    pos += 1
    qualitysegmentmodifers = []
    i = 0
    while i < qualityentrycount:
        temp = readstring(data, pos)
        qualitysegmentmodifers.append(temp[1])
        pos = temp[0]
        i += 1

    seqCount = read32(data, pos)
    pos += 4
    ret = {}
    i = 0

    while i < seqCount:
        firstseg = read32(data, pos)
        pos += 4
        fragPerSeg = read32(data, pos)
        pos += 4
        tmp = i + 1
        ret[tmp] = {"first": firstseg, "total": fragPerSeg}
        i += 1
    return ret


def decode_f4f(fragID, fragData):
    start = fragData.find(b"mdat") + 4
    if fragID > 1:
        (tagLen,) = struct.unpack_from(">L", fragData, start)
        tagLen &= 0x00FFFFFF
        start += tagLen + 11 + 4
    return start
