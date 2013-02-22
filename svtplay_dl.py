#!/usr/bin/env python
import sys
if sys.version_info > (3, 0):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse, parse_qs, unquote_plus, quote_plus
    from io import BytesIO as StringIO
else:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus, quote_plus
    from StringIO import StringIO

import re
import os
import subprocess
from optparse import OptionParser
import xml.etree.ElementTree as ET
import shlex
import json
import time
import logging
import base64
import struct
import binascii
from datetime import timedelta

__version__ = "0.9.2013.02.22"

class Options:
    """
    Options used when invoking the script from another Python script.
    
    Simple container class used when calling get_media() from another Python
    script. The variables corresponds to the command line parameters parsed
    in main() when the script is called directly.
    
    When called from a script there are a few more things to consider:
    
    * Logging is done to 'log'. main() calls setup_log() which sets the
      logging to either stdout or stderr depending on the silent level.
      A user calling get_media() directly can either also use setup_log()
      or configure the log manually.

    * Progress information is printed to 'progress_stream' which defaults to
      sys.stderr but can be changed to any stream.
    
    * Many errors results in calls to system.exit() so catch 'SystemExit'-
      Exceptions to prevent the entire application from exiting if that happens.
    
    """

    def __init__(self):
        self.output = None
        self.resume = False
        self.live = False
        self.silent = False
        self.quality = None
        self.hls = False
        self.other = None
        self.subtitle = False

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr

def readbyte(data, pos):
    return struct.unpack("B", data[pos])[0]

def read16(data, pos):
    endpos = pos + 2
    return struct.unpack(">H", data[pos:endpos])[0]

def read24(data, pos):
    end = pos + 3
    return struct.unpack(">L", "\x00" + data[pos:end])[0]

def read32(data, pos):
    end = pos + 4
    return struct.unpack(">i", data[pos:end])[0]

def read64(data, pos):
    end = pos + 8
    return struct.unpack(">Q", data[pos:end])[0]

def readstring(data, pos):
    length = 0
    while (data[pos + length] != "\x00"):
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

def readbox(data, pos):
    version = readbyte(data, pos)
    pos += 1
    flags = read24(data, pos)
    pos += 3
    bootstrapversion = read32(data, pos)
    pos += 4
    byte = readbyte(data, pos)
    pos += 1
    profile = (byte & 0xC0) >> 6
    live = (byte & 0x20) >> 5
    update = (byte & 0x10) >> 4
    timescale = read32(data, pos)
    pos += 4
    currentmediatime = read64(data, pos)
    pos += 8
    smptetimecodeoffset = read64(data, pos)
    pos += 8
    temp = readstring(data, pos)
    movieidentifier = temp[1]
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
    drm = tmp[1]
    pos = tmp[0]
    tmp = readstring(data, pos)
    metadata = tmp[1]
    pos = tmp[0]
    segmentruntable = readbyte(data, pos)
    pos += 1
    if segmentruntable > 0:
        tmp = readboxtype(data, pos)
        boxtype = tmp[2]
        boxsize = tmp[1]
        pos = tmp[0]
        if boxtype == "asrt":
            antal = readasrtbox(data, pos)
            pos += boxsize
    fragRunTableCount = readbyte(data, pos)
    pos += 1
    i = 0
    while i < fragRunTableCount:
        tmp = readboxtype(data, pos)
        boxtype = tmp[2]
        boxsize = tmp[1]
        pos = tmp[0]
        if boxtype == "afrt":
            readafrtbox(data, pos)
            pos += boxsize
        i += 1
    return antal

def readafrtbox(data, pos):
    version = readbyte(data, pos)
    pos += 1
    flags = read24(data, pos)
    pos += 3
    timescale = read32(data, pos)
    pos += 4
    qualityentry = readbyte(data, pos)
    pos += 1
    i = 0
    while i < qualityentry:
        temp = readstring(data, pos)
        qualitysegmulti = temp[1]
        pos = temp[0]
        i += 1
    fragrunentrycount = read32(data, pos)
    pos += 4
    i = 0
    while i < fragrunentrycount:
        firstfragment = read32(data, pos)
        pos += 4
        timestamp = read64(data, pos)
        pos += 8
        duration = read32(data, pos)
        pos += 4
        i += 1

def readasrtbox(data, pos):
    version = readbyte(data, pos)
    pos += 1
    flags = read24(data, pos)
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

def parsem3u(data):
    if not data.startswith("#EXTM3U"):
        raise ValueError("Does not apprear to be a ext m3u file")

    files = []
    streaminfo = {}
    globdata = {}

    data = data.replace("\r", "\n")
    for l in data.split("\n")[1:]:
        if not l:
            continue
        if l.startswith("#EXT-X-STREAM-INF:"):
            #not a proper parser
            info = [x.strip().split("=", 1) for x in l[18:].split(",")]
            streaminfo.update({info[1][0]: info[1][1]})
        elif l.startswith("#EXT-X-ENDLIST"):
            break
        elif l.startswith("#EXT-X-"):
            globdata.update(dict([l[7:].strip().split(":", 1)]))
        elif l.startswith("#EXTINF:"):
            dur, title = l[8:].strip().split(",", 1)
            streaminfo['duration'] = dur
            streaminfo['title'] = title
        elif l[0] == '#':
            pass
        else:
            files.append((l, streaminfo))
            streaminfo = {}

    return globdata, files

def decode_f4f(fragID, fragData):
    start = fragData.find("mdat") + 4
    if (fragID > 1):
        tagLen, = struct.unpack_from(">L", fragData, start)
        tagLen &= 0x00ffffff
        start  += tagLen + 11 + 4
    return start

def get_http_data(url, method="GET", header="", data=""):
    """ Get the page to parse it for streams """
    request = Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')

    if len(header) > 0:
        request.add_header('Content-Type', header)
    if len(data) > 0:
        request.add_data(data)
    try:
        response = urlopen(request)
    except HTTPError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.code)
        sys.exit(5)
    except URLError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.reason)
        sys.exit(5)
    except ValueError as e:
        log.error("Try adding http:// before the url")
        sys.exit(5)
    if sys.version_info > (3, 0):
        data = response.read()
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
    else:
        try:
            data = response.read()
        except socket.error as e:
            log.error("Lost the connection to the server")
            sys.exit(5)
    response.close()
    return data

def progress(byte, total, extra = ""):
    """ Print some info about how much we have downloaded """
    if total == 0:
         progresstr = "Downloaded %dkB bytes" % (byte >> 10)
         progress_stream.write(progresstr + '\r')
    else:
        ratio = float(byte) / total
        percent = round(ratio*100, 2)
        tlen = str(len(str(total)))
        fmt = "Downloaded %"+tlen+"dkB of %dkB bytes (% 3.2f%%)"
        progresstr = fmt % (byte >> 10, total >> 10, percent)

        columns = int(os.getenv("COLUMNS", "80"))
        if len(progresstr) < columns - 13:
            p = int((columns - len(progresstr) - 3) * ratio)
            q = int((columns - len(progresstr) - 3) * (1 - ratio))
            progresstr = "[" + ("#" * p) + (" " * q) + "] " + progresstr
        progress_stream.write(progresstr + ' ' + extra + '\r')

        if byte >= total:
            progress_stream.write('\n')

    progress_stream.flush()

def download_hds(options, url, swf=None):
    data = get_http_data(url)
    streams = {}
    bootstrap = {}
    xml = ET.XML(data)
    prefix = xml.find("{http://ns.adobe.com/f4m/1.0}id").text

    if sys.version_info < (2, 7):
        bootstrapIter = xml.getiterator("{http://ns.adobe.com/f4m/1.0}bootstrapInfo")
        mediaIter = xml.getiterator("{http://ns.adobe.com/f4m/1.0}media")
    else:
        bootstrapIter = xml.iter("{http://ns.adobe.com/f4m/1.0}bootstrapInfo")
        mediaIter = xml.iter("{http://ns.adobe.com/f4m/1.0}media")

    for i in bootstrapIter:
        bootstrap[i.attrib["id"]] = i.text

    for i in mediaIter:
        streams[int(i.attrib["bitrate"])] = {"url": i.attrib["url"], "bootstrapInfoId": i.attrib["bootstrapInfoId"], "metadata": i.find("{http://ns.adobe.com/f4m/1.0}metadata").text}

    test = select_quality(options, streams)

    bootstrap = base64.b64decode(bootstrap[test["bootstrapInfoId"]])
    box = readboxtype(bootstrap, 0)
    if box[2] == "abst":
        antal = readbox(bootstrap, box[0])

    baseurl = url[0:url.rfind("/")]
    i = 1

    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", options.output)
        if not extension:
            options.output = "%s.flv" % options.output
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    metasize = struct.pack(">L", len(base64.b64decode(test["metadata"])))[1:]
    file_d.write(binascii.a2b_hex(b"464c560105000000090000000012"))
    file_d.write(metasize)
    file_d.write(binascii.a2b_hex(b"00000000000000"))
    file_d.write(base64.b64decode(test["metadata"]))
    file_d.write(binascii.a2b_hex(b"00000000"))
    total = antal[1]["total"]
    start = time.time()
    estimated = ""
    while i <= total:
        url = "%s/%sSeg1-Frag%s" % (baseurl, test["url"], i)
        if options.output != "-":
            progressbar(total, i, estimated)
        data = get_http_data(url)
        number = decode_f4f(i, data)
        file_d.write(data[number:])
        now = time.time()
        dt = now - start
        et = dt / (i + 1) * total
        rt = et - dt
        td = timedelta(seconds = int(rt))
        estimated = "Estimated Remaining: " + str(td)
        i += 1

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

def download_hls(options, url, baseurl=None):
    data = get_http_data(url)
    globaldata, files = parsem3u(data)
    streams = {}
    for i in files:
        streams[int(i[1]["BANDWIDTH"])] = i[0]

    test = select_quality(options, streams)
    if baseurl and test[1:4] != "http":
        test = "%s%s" % (baseurl, test)
    m3u8 = get_http_data(test)
    globaldata, files = parsem3u(m3u8)
    encrypted = False
    key = None
    try:
        keydata = globaldata["KEY"]
        encrypted = True
    except:
        pass

    if encrypted:
        try:
            from Crypto.Cipher import AES
        except ImportError:
            log.error("You need to install pycrypto to download encrypted HLS streams")
            sys.exit(2)
        match = re.search("URI=\"(http://.*)\"", keydata)
        key = get_http_data(match.group(1))
        rand = os.urandom(16)
        decryptor = AES.new(key, AES.MODE_CBC, rand)
    n = 1
    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", options.output)
        if not extension:
            options.output = "%s.ts" % options.output
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    start = time.time()
    estimated = ""
    for i in files:
        item = i[0]
        if options.output != "-":
            progressbar(len(files), n, estimated)
        if item[0:5] != "http:":
            item = "%s/%s" % (baseurl, item)
        data = get_http_data(item)
        if encrypted:
            lots = StringIO(data)

            plain = b""
            crypt = lots.read(1024)
            decrypted = decryptor.decrypt(crypt)
            while decrypted:
                plain += decrypted
                crypt = lots.read(1024)
                decrypted = decryptor.decrypt(crypt)
            data = plain

        file_d.write(data)
        now = time.time()
        dt = now - start
        et = dt / (n + 1) * len(files)
        rt = et - dt
        td = timedelta(seconds = int(rt))
        estimated = "Estimated Remaining: " + str(td)
        n += 1

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

def download_http(options, url):
    """ Get the stream from HTTP """
    response = urlopen(url)
    try:
        total_size = response.info()['Content-Length']
    except KeyError:
        total_size = 0
    total_size = int(total_size)
    bytes_so_far = 0
    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", url)
        if extension:
            options.output = options.output + extension.group(1)
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    lastprogress = 0
    while 1:
        chunk = response.read(8192)
        bytes_so_far += len(chunk)

        if not chunk:
            break

        file_d.write(chunk)
        if options.output != "-":
            now = time.time()
            if lastprogress + 1 < now:
                lastprogress = now
                progress(bytes_so_far, total_size)

    if options.output != "-":
        file_d.close()

def download_rtmp(options, url):
    """ Get the stream from RTMP """
    args = []
    if options.live:
        args.append("-v")

    if options.resume:
        args.append("-e")

    extension = re.search("(\.[a-z0-9]+)$", url)
    if options.output != "-":
        if not extension:
            extension = re.search("-y (.+):[-_a-z0-9\/]", options.other)
            if not extension:
                options.output = "%s.flv" % options.output
            else:
                options.output = "%s.%s" % (options.output, extension.group(1))
        else:
            options.output = options.output + extension.group(1)
        log.info("Outfile: %s", options.output)
        args += ["-o", options.output]
    if options.silent or options.output == "-":
        args.append("-q")
    if options.other:
        if sys.version_info < (3, 0):
            args += shlex.split(options.other.encode("utf-8"))
        else:
            args += shlex.split(options.other)
    command = ["rtmpdump", "-r", url] + args
    try:
        subprocess.call(command)
    except OSError as e:
        log.error("Could not execute rtmpdump: " + e.strerror)

def timestr(seconds):
    total = float(seconds) / 1000
    hours = int(total / 3600)
    minutes = int(total / 60)
    sec = total % 60
    output = "%02d:%02d:%02.02f" % (hours, minutes, sec)
    return output.replace(".", ",")

def norm(name):
    if name[0] == "{":
        uri, tag = name[1:].split("}")
        return tag
    else:
        return name

def subtitle_tt(options, url):
    i = 1
    data = ""
    skip = False
    fh = get_http_data(url)
    tree = ET.parse(fh)
    for node in tree.iter():
        tag = norm(node.tag)
        if tag == "p":
            if skip:
                data = data + "\n"
            data += '%s\n%s,%s --> %s,%s\n' % (i, node.attrib["begin"][:8], node.attrib["begin"][9:], node.attrib["end"][:8], node.attrib["end"][9:])
            data += '%s\n' % node.text.strip(' \t\n\r')
            skip = True
            i += 1
        if tag == "br":
            if node.tail:
                data += '%s\n\n' % node.tail.strip(' \t\n\r')
                skip = False
    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(data)
    fd.close()

def subtitle_json(options, url):
    data = json.loads(get_http_data(url))
    number = 1
    subs = ""
    for i in data:
        subs += "%s\n%s --> %s\n" % (number, timestr(int(i["startMillis"])), timestr(int(i["endMillis"])))
        subs += "%s\n\n" % i["text"]
        number += 1

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_sami(options, url):
    data = get_http_data(url)
    tree = ET.XML(data)
    subt = tree.find("Font")
    subs = ""
    for i in subt.getiterator():
        if i.tag == "Subtitle":
            if i.attrib["SpotNumber"] == 1:
                subs += "%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
            else:
                subs += "\n%s\n%s --> %s\n" % (i.attrib["SpotNumber"], i.attrib["TimeIn"], i.attrib["TimeOut"])
        else:
            subs += "%s\n" % i.text

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_smi(options, url):
    data = get_http_data(url)
    recomp = re.compile(r'<SYNC Start=(\d+)>\s+<P Class=\w+>(.*)<br>\s+<SYNC Start=(\d+)>\s+<P Class=\w+>', re.M|re.I|re.U)
    number = 1
    subs = ""
    for i in recomp.finditer(data):
        subs += "%s\n%s --> %s\n" % (number, timestr(i.group(1)), timestr(i.group(3)))
        text = "%s\n\n" % i.group(2)
        subs += text.replace("<br>", "\n")
        number += 1

    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(subs)
    fd.close()

def subtitle_wsrt(options, url):
    data = get_http_data(url)
    recomp = re.compile("(\d+)\r\n([\d:\.]+ --> [\d:\.]+)?([^\r\n]+)?\r\n([^\r\n]+)\r\n(([^\r\n]*)\r\n)?")
    srt = ""
    for i in recomp.finditer(data):
        sub = "%s\n%s\n%s\n" % (i.group(1), i.group(2).replace(".", ","), i.group(4))
        if len(i.group(6)) > 0:
            sub += "%s\n" % i.group(6)
        sub += "\n"
        sub = re.sub('<[^>]*>', '', sub)
        srt += sub
    filename = re.search("(.*)\.[a-z0-9]{2,3}$", options.output)
    if filename:
        options.output = "%s.srt" % filename.group(1)
    log.info("Subtitle: %s", options.output)
    fd = open(options.output, "w")
    fd.write(srt)
    fd.close()

def select_quality(options, streams):
    sort = sorted(streams.keys(), key=int)

    if options.quality:
        quality = options.quality
    else:
        quality = sort.pop()

    try:
        selected = streams[int(quality)]
    except (KeyError, ValueError):
        log.error("Can't find that quality. (Try one of: %s)",
                      ", ".join(map(str, sort)))
        sys.exit(4)

    return selected

class Justin():
    def handle(self, url):
        return ("twitch.tv" in url) or ("justin.tv" in url)

    def get(self, options, url):
        parse = urlparse(url)
        match = re.search("/b/(\d+)", parse.path)
        if match:
            url = "http://api.justin.tv/api/broadcast/by_archive/%s.xml?onsite=true" % match.group(1)
            data = get_http_data(url)
            xml = ET.XML(data)
            url = xml.find("archive").find("video_file_url").text

            download_http(options, url)
        else:
            match = re.search("/(.*)", parse.path)
            if match:
                user = match.group(1)
                data = get_http_data(url)
                match = re.search("embedSWF\(\"(.*)\", \"live", data)
                if not match:
                    log.error("Can't find swf file.")
                options.other = match.group(1)
                url = "http://usher.justin.tv/find/%s.xml?type=any&p=2321" % user
                options.live = True
                data = get_http_data(url)
                data = re.sub("<(\d+)", "<_\g<1>", data)
                data = re.sub("</(\d+)", "</_\g<1>", data)
                xml = ET.XML(data)
                if sys.version_info < (2, 7):
                    sa = list(xml)
                else:
                    sa = list(xml)
                streams = {}
                for i in sa:
                    if i.tag[1:][:-1] != "iv":
                        try:
                            stream = {}
                            stream["token"] = i.find("token").text
                            stream["url"] = "%s/%s" % (i.find("connect").text, i.find("play").text)
                            streams[int(i.find("video_height").text)] = stream
                        except AttributeError:
                            pass

                test = select_quality(options, streams)
                options.other = "-j '%s' -W %s" % (test["token"], options.other)
                options.resume = False
                download_rtmp(options, test["url"])

class Hbo():
    def handle(self, url):
        return "hbo.com" in url

    def get(self, url):
        parse = urlparse(url)
        try:
            other = parse[5]
        except KeyError:
            log.error("Something wrong with that url")
            sys.exit(2)
        match = re.search("^/(.*).html", other)
        if not match:
            log.error("Cant find video file")
            sys.exit(2)
        url = "http://www.hbo.com/data/content/%s.xml" % match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        videoid = xml.find("content")[1].find("videoId").text
        url = "http://render.cdn.hbo.com/data/content/global/videos/data/%s.xml" % videoid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("videos")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("size"))
        else:
            sa = list(ss.iter("size"))
        streams = {}
        for i in sa:
            stream = {}
            stream["path"] = i.find("tv14").find("path").text
            streams[int(i.attrib["width"])] = stream

        test = select_quality(options, streams)

        download_rtmp(options, test["path"])

class Sr():
    def handle(self, url):
        return "sverigesradio.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        parse = urlparse(url)
        try:
            metafile = parse_qs(parse[4])["metafile"][0]
            options.other = "%s?%s" % (parse[2], parse[4])
        except KeyError:
            match = re.search("linkUrl=(.*)\;isButton=", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            options.other = unquote_plus(match.group(1))
        url = "http://sverigesradio.se%s" % options.other
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("entry").find("ref").attrib["href"]
        download_http(options, url)

class Urplay():
    def handle(self, url):
        return ("urplay.se" in url) or ("ur.se" in url)

    def get(self, options, url):
        data = get_http_data(url)
        data = re.search("urPlayer.init\((.*)\);", data)
        data = re.sub("(\w+): ", r'"\1":',data.group(1))
        data = data.replace("\'", "\"").replace("\",}","\"}").replace("(m = location.hash.match(/[#&]start=(\d+)/)) ? m[1] : 0,","0")
        jsondata = json.loads(data)
        subtitle = jsondata["subtitles"].split(",")[0]
        basedomain = jsondata["streaming_config"]["streamer"]["redirect"]
        http = "http://%s/%s" % (basedomain, jsondata["file_html5"])
        hds = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hds_file"])
        hls = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        rtmp = "rtmp://%s/%s" % (basedomain, jsondata["streaming_config"]["rtmp"]["application"])
        path = "mp%s:%s" % (jsondata["file_flash"][-1], jsondata["file_flash"])
        options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], path)
        if options.hls:
            download_hls(options, hls, http)
        else:
            download_rtmp(options, rtmp)
        if options.subtitle:
            if options.output != "-":
                subtitle_tt(options, subtitle)

class Qbrick():
    def handle(self, url):
        return ("dn.se" in url) or ("di.se" in url) or ("svd.se" in url)

    def get(self, options, url):
        if re.findall("dn.se", url):
            data = get_http_data(url)
            match = re.search("data-qbrick-mcid=\"([0-9A-F]+)\"", data)
            if not match:
                match = re.search("mediaId = \'([0-9A-F]+)\';", data)
                if not match:
                    log.error("Can't find video file")
                    sys.exit(2)
                mcid = "%sDE1BA107" % match.group(1)
            else:
                mcid = match.group(1)
            host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/%s" % mcid
        elif re.findall("di.se", url):
            data = get_http_data(url)
            match = re.search("ccid: \"(.*)\"\,", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            host = "http://vms.api.qbrick.com/rest/v3/getplayer/%s" % match.group(1)
        elif re.findall("svd.se", url):
            match = re.search("_([0-9]+)\.svd", url)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            data = get_http_data("http://www.svd.se/?service=ajax&type=webTvClip&articleId=%s" % match.group(1))
            match = re.search("mcid=([A-F0-9]+)\&width=", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/%s" % match.group(1)
        else:
            log.error("Can't find site")
            sys.exit(2)

        data = get_http_data(host)
        xml = ET.XML(data)
        try:
            url = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            log.error("Can't find video file")
            sys.exit(2)

        data = get_http_data(url)
        xml = ET.XML(data)
        server = xml.find("head").find("meta").attrib["base"]
        streams = xml.find("body").find("switch")
        if sys.version_info < (2, 7):
            sa = list(streams.getiterator("video"))
        else:
            sa = list(streams.iter("video"))
        streams = {}
        for i in sa:
            streams[int(i.attrib["system-bitrate"])] = i.attrib["src"]

        path = select_quality(options, streams)

        options.other = "-y %s" % path
        download_rtmp(options, server)

class Kanal5():
    def handle(self, url):
        return ("kanal5play.se" in url) or ("kanal9play.se" in url)

    def get(self, options, url):
        match = re.search(".*video/([0-9]+)", url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://www.kanal5play.se/api/getVideo?format=FLASH&videoId=%s" % match.group(1)
        data = json.loads(get_http_data(url))
        options.live = data["isLive"]
        steambaseurl = data["streamBaseUrl"]
        if data["hasSubtitle"]:
            subtitle = "http://www.kanal5play.se/api/subtitles/%s" % match.group(1)
        streams = {}

        for i in data["streams"]:
            stream = {}
            stream["source"] = i["source"]
            streams[int(i["bitrate"])] = stream

        test = select_quality(options, streams)

        filename = test["source"]
        match = re.search("^(.*):", filename)
        options.output  = "%s.%s" % (options.output, match.group(1))
        options.other = "-W %s -y %s " % ("http://www.kanal5play.se/flash/StandardPlayer.swf", filename)
        download_rtmp(options, steambaseurl)
        if options.subtitle:
            if options.output != "-":
                subtitle_json(options, subtitle)

class Expressen():
    def handle(self, url):
        return "expressen.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search("xmlUrl: '(http://www.expressen.*)'", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("vurls")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("vurl"))
        else:
            sa = list(ss.iter("vurl"))
        streams = {}

        for i in sa:
            streams[int(i.attrib["bitrate"])] = i.text

        test = select_quality(options, streams)

        filename = test
        match = re.search("rtmp://([0-9a-z\.]+/[0-9]+/)(.*)", filename)

        filename = "rtmp://%s" % match.group(1)
        options.other = "-y %s" % match.group(2)

        download_rtmp(options, filename)

class Aftonbladet():
    def handle(self, url):
        return "aftonbladet.se" in url

    def get(self, options, url):
        parse = urlparse(url)
        data = get_http_data(url)
        match = re.search("abTvArticlePlayer-player-(.*)-[0-9]+-[0-9]+-clickOverlay", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        try:
            start = parse_qs(parse[4])["start"][0]
        except KeyError:
            start = 0
        url = "http://www.aftonbladet.se/resource/webbtv/article/%s/player" % match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("articleElement").find("mediaElement").find("baseUrl").text
        path = xml.find("articleElement").find("mediaElement").find("media").attrib["url"]
        live = xml.find("articleElement").find("mediaElement").find("isLive").text
        options.other = "-y %s" % path

        if start > 0:
            options.other = "%s -A %s" % (options.other, str(start))

        if live == "true":
            options.live = True

        if url == None:
            log.error("Can't find any video on that page")
            sys.exit(3)

        if url[0:4] == "rtmp":
            download_rtmp(options, url)
        else:
            filename = url + path
            download_http(options, filename)

class Viaplay():
    def handle(self, url):
        return ("tv3play.se" in url) or ("tv6play.se" in url) or ("tv8play.se" in url)

    def get(self, options, url):
        parse = urlparse(url)
        match = re.search('\/play\/(.*)/?', parse.path)
        if not match:
            log.error("Cant find video file")
            sys.exit(2)
        url = "http://viastream.viasat.tv/PlayProduct/%s" % match.group(1)
        options.other = ""
        data = get_http_data(url)
        xml = ET.XML(data)
        filename = xml.find("Product").find("Videos").find("Video").find("Url").text
        subtitle = xml.find("Product").find("SamiFile").text

        if filename[:4] == "http":
            data = get_http_data(filename)
            xml = ET.XML(data)
            filename = xml.find("Url").text

        options.other = "-W http://flvplayer.viastream.viasat.tv/play/swf/player110516.swf?rnd=1315434062"
        download_rtmp(options, filename)
        if options.subtitle and subtitle:
            if options.output != "-":
                subtitle_sami(options, subtitle)

class Tv4play():
    def handle(self, url):
        return ("tv4play.se" in url) or ("tv4.se" in url)

    def get(self, options, url):
        parse = urlparse(url)
        if "tv4play.se" in url:
            try:
                vid = parse_qs(parse[4])["video_id"][0]
            except KeyError:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            match = re.search("-(\d+)$", url)
            if match:
                vid = match.group(1)
            else:
                data = get_http_data(url)
                match = re.search("\"vid\":\"(\d+)\",", data)
                if match:
                    vid = match.group(1)
                else:
                    log.error("Can't find video file")
                    sys.exit(2)

        url = "http://premium.tv4play.se/api/web/asset/%s/play" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            if xml.find("live").text != "false":
                options.live = True

        streams = {}
        subtitle = False

        for i in sa:
            if i.find("mediaFormat").text != "smi":
                stream = {}
                stream["uri"] = i.find("base").text
                stream["path"] = i.find("url").text
                streams[int(i.find("bitrate").text)] = stream
            elif i.find("mediaFormat").text == "smi":
                subtitle = i.find("url").text
        if len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
        options.other = "-W %s -y %s" % (swf, test["path"])

        if test["uri"][0:4] == "rtmp":
            download_rtmp(options, test["uri"])
        elif test["uri"][len(test["uri"])-3:len(test["uri"])] == "f4m":
            match = re.search("\/se\/secure\/", test["uri"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["path"]
            download_hds(options, manifest, swf)
        if options.subtitle and subtitle:
            if options.output != "-":
                subtitle_smi(options, subtitle)

class Svtplay():
    def handle(self, url):
        return ("svtplay.se" in url) or ("svt.se" in url)

    def get(self, options, url):
        if re.findall("svt.se", url):
            data = get_http_data(url)
            match = re.search("data-json-href=\"(.*)\"", data)
            if match:
                filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
                url = "http://www.svt.se%s" % filename
            else:
                log.error("Can't find video file")
                sys.exit(2)
        url = "%s?type=embed" % url
        data = get_http_data(url)
        match = re.search("value=\"(/(public)?(statiskt)?/swf/video/svtplayer-[0-9\.]+swf)\"", data)
        swf = "http://www.svtplay.se%s" % match.group(1)
        options.other = "-W %s" % swf
        url = "%s&output=json&format=json" % url
        data = json.loads(get_http_data(url))
        options.live = data["video"]["live"]
        streams = {}
        streams2 = {} #hack..
        for i in data["video"]["videoReferences"]:
            if options.hls and i["playerType"] == "ios":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            elif not options.hls and i["playerType"] == "flash":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            if options.hls and i["playerType"] == "flash":
                stream = {}
                stream["url"] = i["url"]
                streams2[int(i["bitrate"])] = stream

        if len(streams) == 0 and options.hls:
            test = streams2[0]
            test["url"] = test["url"].replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        elif len(streams) == 0:
            log.error("Can't find any streams.")
            sys.exit(2)
        elif len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        if test["url"][0:4] == "rtmp":
            download_rtmp(options, test["url"])
        elif options.hls:
            download_hls(options, test["url"])
        elif test["url"][len(test["url"])-3:len(test["url"])] == "f4m":
            match = re.search("\/se\/secure\/", test["url"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["url"]
            download_hds(options, manifest, swf)
        else:
            download_http(options, test["url"])
        if options.subtitle:
            try:
                suburl = data["video"]["subtitleReferences"][0]["url"]
            except KeyError:
                sys.exit(1)
            if len(suburl) > 0:
                if options.output != "-":
                    subtitle_wsrt(options, suburl)

class Nrk(object):
    def handle(self, url):
        return "nrk.no" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'data-media="(.*manifest.f4m)"', data)
        manifest_url = match.group(1)
        if options.hls:
            manifest_url = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
            download_hls(options, manifest_url)
        else:
            manifest_url = "%s?hdcore=2.8.0&g=hejsan" % manifest_url
            download_hds(options, manifest_url)

class Dr(object):
    def handle(self, url):
        return "dr.dk" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        resource_url = match.group(1)
        resource_data = get_http_data(resource_url)
        resource = json.loads(resource_data)
        streams = {}
        for stream in resource['links']:
            streams[stream['bitrateKbps']] = stream['uri']
        if len(streams) == 1:
            uri = streams[list(streams.keys())[0]]
        else:
            uri = select_quality(options, streams)
        # need -v ?
        options.other = "-v -y '" + uri.replace("rtmp://vod.dr.dk/cms/", "") + "'"
        download_rtmp(options, uri)

class Ruv(object):
    def handle(self, url):
        return "ruv.is" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'(http://load.cache.is/vodruv.*)"', data)
        js_url = match.group(1)
        js = get_http_data(js_url)
        tengipunktur = js.split('"')[1]
        match = re.search(r"http.*tengipunktur [+] '([:]1935.*)'", data)
        m3u8_url = "http://" + tengipunktur + match.group(1)
        base_url = m3u8_url.rsplit("/", 1)[0]
        download_hls(options, m3u8_url, base_url)

class Radioplay(object):
    def handle(self, url):
        return "radioplay.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search("liveStationsRedundancy = ({.*});</script>", data)
        parse = urlparse(url)
        station = parse.path[1:]
        streams = None
        if match:
            data = json.loads(match.group(1))
            for i in data["stations"]:
                if station == i["name"].lower().replace(" ", ""):
                    streams = i["streams"]
                    break
        else:
            log.error("Can't find any streams.")
            sys.exit(2)
        if streams:
            if options.hls:
                try:
                    m3u8_url = streams["hls"]
                    base_url = m3u8_url.rsplit("/", 1)[0]
                    download_hls(options, m3u8_url, base_url)
                except KeyError:
                    log.error("Can't find any streams.")
                    sys.error(2)
            else:
                try:
                    rtmp = streams["rtmp"]
                    download_rtmp(options, rtmp)
                except KeyError:
                    mp3 = streams["mp3"]
                    download_http(options, mp3)

        else:
            log.error("Can't find any streams.")
            sys.exit(2)

class generic(object):
    ''' Videos embed in sites '''
    def get(self, sites, url):
        data = get_http_data(url)
        match = re.search("src=\"(http://www.svt.se/wd.*)\" frameborder", data)
        stream = None
        if match:
            url = match.group(1)
            for i in sites:
                if i.handle(url):
                    stream = i
                    break
        return url, stream

def progressbar(total, pos, msg=""):
    """
    Given a total and a progress position, output a progress bar
    to stderr. It is important to not output anything else while
    using this, as it relies soley on the behavior of carriage
    return (\\r).

    Can also take an optioal message to add after the
    progressbar. It must not contain newliens.

    The progress bar will look something like this:

    [099/500][=========...............................] ETA: 13:36:59

    Of course, the ETA part should be supplied be the calling
    function.
    """
    width = 50 # TODO hardcoded progressbar width
    rel_pos = int(float(pos)/total*width)
    bar = str()

    # FIXME ugly generation of bar
    for i in range(0, rel_pos):
        bar += "="
    for i in range(rel_pos, width):
        bar += "."

    # Determine how many digits in total (base 10)
    digits_total = len(str(total))
    fmt_width = "%0" + str(digits_total) + "d"
    fmt = "\r[" + fmt_width + "/" + fmt_width + "][%s] %s"

    progress_stream.write(fmt % (pos, total, bar, msg))

def get_media(url, options):
    sites = [Aftonbladet(), Dr(), Expressen(), Hbo(), Justin(), Kanal5(), Nrk(),
            Qbrick(), Ruv(), Radioplay(), Sr(), Svtplay(), Tv4play(), Urplay(), Viaplay()]
    stream = None
    for i in sites:
        if i.handle(url):
            stream = i
            break

    if not stream:
        url, stream = generic().get(sites, url)
        if not stream:
            log.error("That site is not supported. Make a ticket or send a message")
            sys.exit(2)
    url = url.replace("&amp;", "&")
    if not options.output or os.path.isdir(options.output):
        data = get_http_data(url)
        match = re.search("(?i)<title.*>\s*(.*?)\s*</title>", data)
        if match:
            if sys.version_info > (3, 0):
                title = re.sub('[^\w\s-]', '', match.group(1)).strip().lower()
                if options.output:
                    options.output = options.output + re.sub('[-\s]+', '-', title)
                else:
                    options.output = re.sub('[-\s]+', '-', title)
            else:
                title = unicode(re.sub('[^\w\s-]', '', match.group(1)).strip().lower())
                if options.output:
                    options.output = unicode(options.output + re.sub('[-\s]+', '-', title))
                else:
                    options.output = unicode(re.sub('[-\s]+', '-', title))

    stream.get(options, url)

def setup_log(silent):
    if silent:
        stream = sys.stderr
        level = logging.WARNING
    else:
        stream = sys.stdout
        level = logging.INFO

    fmt = logging.Formatter('%(levelname)s %(message)s')
    hdlr = logging.StreamHandler(stream)
    hdlr.setFormatter(fmt)

    log.addHandler(hdlr)
    log.setLevel(level)

def main():
    """ Main program """
    usage = "usage: %prog [options] url"
    parser = OptionParser(usage=usage, version=__version__)
    parser.add_option("-o", "--output",
        metavar="OUTPUT", help="Outputs to the given filename.")
    parser.add_option("-r", "--resume",
        action="store_true", dest="resume", default=False,
        help="Resume a download")
    parser.add_option("-l", "--live",
        action="store_true", dest="live", default=False,
        help="Enable for live streams")
    parser.add_option("-s", "--silent",
        action="store_true", dest="silent", default=False)
    parser.add_option("-q", "--quality",
        metavar="quality", help="Choose what format to download.\nIt will download the best format by default")
    parser.add_option("-H", "--hls",
        action="store_true", dest="hls", default=False)
    parser.add_option("-S", "--subtitle",
        action="store_true", dest="subtitle", default=False,
        help="Download subtitle from the site if available.")
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    setup_log(options.silent)

    url = args[0]
    get_media(url, options)

if __name__ == "__main__":
    main()
