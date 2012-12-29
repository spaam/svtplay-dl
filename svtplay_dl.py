#!/usr/bin/env python
import sys
if sys.version_info > (3, 0):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse, parse_qs, unquote_plus, quote_plus
    from io import StringIO
else:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus, quote_plus
    import StringIO

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

__version__ = "0.8.2012.12.23"

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

    data = data.replace("\r","\n")
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

def decode_f4f(fragID, fragData ):
    start = fragData.find( "mdat" ) + 4
    if (fragID > 1):
        for dummy in range( 2 ):
            tagLen, = struct.unpack_from( ">L", fragData, start )
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
        data = response.read().decode('utf-8')
    else:
        try:
            data = response.read()
        except socket.error as e:
            log.error("Lost the connection to the server")
            sys.exit(5)
    response.close()
    return data

def progress(byte, total):
    """ Print some info about how much we have downloaded """
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
    progress_stream.write(progresstr + '\r')

    if byte >= total:
        progress_stream.write('\n')

    progress_stream.flush()

def download_hds(options, url, swf):
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
            options.output = options.output + ".flv"
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    file_d.write(binascii.a2b_hex( "464c56010500000009000000001200010c00000000000000" ) )
    file_d.write(base64.b64decode(test["metadata"]))
    file_d.write(binascii.a2b_hex("00000000"))

    while i <= antal[1]["total"]:
        url = "%s/%sSeg1-Frag%s" % (baseurl, test["url"], i)
        if options.output != "-":
            progressbar(antal[1]["total"], i)
        data = get_http_data(url)
        number = decode_f4f(i, data)
        file_d.write(data[number:])
        i += 1

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

def download_hls(options, url):
    data = get_http_data(url)
    globaldata, files = parsem3u(data)
    streams = {}
    for i in files:
        streams[int(i[1]["BANDWIDTH"])] = i[0]

    test = select_quality(options, streams)
    m3u8 = get_http_data(test)
    globaldata, files = parsem3u(m3u8)
    encrypted = False
    key = None
    try:
        keydata = globaldata["KEY"]
        encrypted = True
        match = re.search("URI=\"(http://.*)\"", keydata)
        key = get_http_data(match.group(1))
        rand = os.urandom(16)
    except:
        pass

    try:
        from Crypto.Cipher import AES
        decryptor = AES.new(key, AES.MODE_CBC, rand)
    except ImportError:
        log.error("You need to install pycrypto to download encrypted HLS streams")
        sys.exit(2)
    n = 1
    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", options.output)
        if not extension:
            options.output = options.output + ".ts"
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    for i in files:
        if options.output != "-":
            progressbar(len(files), n)
        data = get_http_data(i[0])
        if encrypted:
            lots = StringIO.StringIO(data)

            plain = ""
            crypt = lots.read(1024)
            decrypted = decryptor.decrypt(crypt)
            while decrypted:
                plain += decrypted
                crypt = lots.read(1024)
                decrypted = decryptor.decrypt(crypt)
            data = plain

        file_d.write(data)
        n += 1

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

def download_http(options, url):
    """ Get the stream from HTTP """
    response = urlopen(url)
    total_size = response.info()['Content-Length']
    total_size = int(total_size)
    bytes_so_far = 0
    if options.output != "-":
        extension = re.search("(\.[a-z0-9]+)$", url)
        if extension:
            options.output = options.output + extension.group(1)
        log.info("Outfile: %s", options.output)
        file_d = open(options.output,"wb")
    else:
        file_d = sys.stdout

    lastprogress = 0
    while 1:
        chunk = response.read(8192)
        bytes_so_far += len(chunk)

        if not chunk:
            break

        file_d.write(chunk)
        if output != "-":
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
                options.output = options.output + ".flv"
            else:
                options.output = options.output + "." + extension.group(1)
        else:
            options.output = options.output + extension.group(1)
        log.info("Outfile: %s", options.output)
        args += ["-o", options.output]
    if options.silent or options.output == "-":
        args.append("-q")
    if options.other:
        args += shlex.split(options.other)
    command = ["rtmpdump", "-r", url] + args
    try:
        subprocess.call(command)
    except OSError as e:
        log.error("Could not execute rtmpdump: " + e.strerror)

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
    def get(self, options, url):
        options.other = "-a ondemand"
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
                    stream["url"] = i.find("connect").text + "/" + i.find("play").text
                    streams[int(i.find("video_height").text)] = stream
                except AttributeError:
                    None

        test = select_quality(options, streams)
        options.other = "-j '%s' -W %s" % (test["token"], options.resume)
        options.resume = False
        download_rtmp(options, test["url"])

class Justin2():
    def get(self, options, url):
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("archive").find("video_file_url").text

        download_http(url, options.output)

class Hbo():
    def get(self, url):
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
    def get(self, options, url):
        url = url + options.other
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("entry").find("ref").attrib["href"]

        download_http(url, options.output)

class Urplay():
    def get(self, options, url):
        data = get_http_data(url)
        match = re.search('file=(.*)\&plugins', data)
        if match:
            path = "mp" + match.group(1)[-1] + ":" + match.group(1)
            options.other = "-a ondemand -y %s" % path

            download_rtmp(options, "rtmp://streaming.ur.se/")

class Qbrick():
    def get(self, options, url):
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
    def get(self, options, url):
        data = json.loads(get_http_data(url))
        options.live = data["isLive"]
        steambaseurl = data["streamBaseUrl"]
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

class Kanal9():
    def get(self, options, url):
        try:
            from pyamf import remoting
        except ImportError:
            log.error("You need to install pyamf to download content from kanal5 and kanal9")
            log.error("In debian the package is called python-pyamf")
            sys.exit(2)

        player_id = 811317479001
        publisher_id = 22710239001
        const = "9f79dd85c3703b8674de883265d8c9e606360c2e"
        env = remoting.Envelope(amfVersion=3)
        env.bodies.append(("/1", remoting.Request(target="com.brightcove.player.runtime.PlayerMediaFacade.findMediaById", body=[const, player_id, options.other, publisher_id], envelope=env)))
        env = str(remoting.encode(env).read())
        url = "http://" + url + "/services/messagebroker/amf?playerKey=AQ~~,AAAABUmivxk~,SnCsFJuhbr0vfwrPJJSL03znlhz-e9bk"
        header = "application/x-amf"
        data = get_http_data(url, "POST", header, env)
        streams = {}

        for i in remoting.decode(data).bodies[0][1].body['renditions']:
            stream = {}
            stream["uri"] = i["defaultURL"]
            streams[i["encodingRate"]] = stream

        test = select_quality(options, streams)

        filename = test["uri"]
        match = re.search("(rtmp[e]{0,1}://.*)\&(.*)$", filename)
        options.other = "-W %s -y %s " % ("http://admin.brightcove.com/viewer/us1.25.04.01.2011-05-24182704/connection/ExternalConnection_2.swf", match.group(2))
        download_rtmp(options, match.group(1))

class Expressen():
    def get(self, options, url):
        other = ""
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
        match = re.search("rtmp://([0-9a-z\.]+/[0-9]+/)(.*).flv", filename)

        filename = "rtmp://%s" % match.group(1)
        options.other = "-y %s" % match.group(2)

        download_rtmp(options, filename)

class Aftonbladet():
    def get(self, options, url, start):
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("articleElement").find("mediaElement").find("baseUrl").text
        path = xml.find("articleElement").find("mediaElement").find("media").attrib["url"]
        options.other = "-y %s" % path

        if start > 0:
            options.other = options.other + " -A %s" % str(start)

        if url == None:
            log.error("Can't find any video on that page")
            sys.exit(3)

        if url[0:4] == "rtmp":
            download_rtmp(options, url)
        else:
            filename = url + path
            download_http(options, filename)

class Viaplay():
    def get(self, options, url):
        options.other = ""
        data = get_http_data(url)
        xml = ET.XML(data)
        filename = xml.find("Product").find("Videos").find("Video").find("Url").text

        if filename[:4] == "http":
            data = get_http_data(filename)
            xml = ET.XML(data)
            filename = xml.find("Url").text

        options.other = "-W http://flvplayer.viastream.viasat.tv/play/swf/player110516.swf?rnd=1315434062"
        download_rtmp(options, filename)

class Tv4play():
    def get(self, options, url):
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))
        
        if xml.find("live").text:
            options.live = True

        streams = {}
        sa.pop(len(sa)-1)

        for i in sa:
            stream = {}
            stream["uri"] = i.find("base").text
            stream["path"] = i.find("url").text
            streams[int(i.find("bitrate").text)] = stream

        if len(streams) == 1:
            test = streams[streams.keys()[0]]
        else:
            test = select_quality(options, streams)

        swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
        options.other = "-W %s -y %s" % (swf, test["path"])

        if test["uri"][0:4] == "rtmp":
            download_rtmp(options, test["uri"], options.output, options.live, options.other, options.resume)
        elif test["uri"][len(test["uri"])-3:len(test["uri"])] == "f4m":
            match = re.search("\/se\/secure\/", test["uri"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["path"]
            download_hds(options, manifest, swf)

class Svtplay():
    def get(self, options, url):
        url = url + "?type=embed"
        data = get_http_data(url)
        match = re.search("value=\"(/(public)?(statiskt)?/swf/video/svtplayer-[0-9\.]+swf)\"", data)
        swf = "http://www.svtplay.se" + match.group(1)
        options.other = "-W " + swf
        url = url + "&output=json&format=json"
        data = json.loads(get_http_data(url))
        options.live = data["video"]["live"]
        streams = {}

        for i in data["video"]["videoReferences"]:
            if options.hls and i["playerType"] == "ios":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            elif not options.hls and i["playerType"] == "flash":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream

        if len(streams) == 0:
            log.error("Can't find any streams.")
            sys.exit(2)
        elif len(streams) == 1:
            test = streams[streams.keys()[0]]
        else:
            test = select_quality(options, streams)

        if test["url"][0:4] == "rtmp":
            download_rtmp(options, test["url"], options.output, options.live, options.other, options.resume)
        elif options.hls:
            download_hls(options, test["url"], options.output, options.live, options.other)
        elif test["url"][len(test["url"])-3:len(test["url"])] == "f4m":
            match = re.search("\/se\/secure\/", test["url"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["url"]
            download_hds(options, manifest, swf)
        else:
            download_http(options, test["url"])

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
    if not options.output or os.path.isdir(options.output):
        data = get_http_data(url)
        match = re.search("(?i)<title>\s*(.*?)\s*</title>", data)
        if match:
            if sys.version_info > (3, 0):
                title = re.sub('[^\w\s-]', '', match.group(1)).strip().lower()
                if output:
                    options.output = options.output + re.sub('[-\s]+', '-', title)
                else:
                    options.output = re.sub('[-\s]+', '-', title)
            else:
                title = unicode(re.sub('[^\w\s-]', '', match.group(1)).strip().lower())
                if options.output:
                    options.output = unicode(options.output + re.sub('[-\s]+', '-', title))
                else:
                    options.output = unicode(re.sub('[-\s]+', '-', title))

    if re.findall("(twitch|justin).tv", url):
        parse = urlparse(url)
        match = re.search("/b/(\d+)", parse.path)
        if match:
            url = "http://api.justin.tv/api/broadcast/by_archive/%s.xml?onsite=true" % match.group(1)
            Justin2().get(options, url)
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
                Justin().get(options, url)

    if re.findall("hbo.com", url):
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
        url = "http://www.hbo.com/data/content/" + match.group(1) + ".xml"
        Hbo().get(options, url)

    if re.findall("tv4play", url):
        parse = urlparse(url)
        try:
            vid = parse_qs(parse[4])["video_id"][0]
        except KeyError:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://premium.tv4play.se/api/web/asset/%s/play" % vid
        Tv4play().get(options, url)

    elif re.findall("(tv3play|tv6play|tv8play)", url):
        parse = urlparse(url)
        match = re.search('\/play\/(.*)/?', parse.path)
        if not match:
            log.error("Cant find video file")
            sys.exit(2)
        url = "http://viastream.viasat.tv/PlayProduct/%s" % match.group(1)
        Viaplay().get(options, url)

    elif re.findall("viaplay", url):
        parse = urlparse(url)
        match = re.search('\/Tv/channels\/[a-zA-Z0-9-]+\/[a-zA-Z0-9-]+\/[a-zA-Z0-9-]+\/(.*)/', parse.path)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://viasat.web.entriq.net/nw/article/view/%s/?tf=players/TV6.tpl" % match.group(1)
        data = get_http_data(url)
        match = re.search("id:'(.*)'", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://viastream.viasat.tv/PlayProduct/%s" % match.group(1)
        Viaplay().get(options, url)

    elif re.findall("aftonbladet", url):
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
        Aftonbladet().get(options, url, start)

    elif re.findall("expressen", url):
        parse = urlparse(url)
        match = re.search("/(.*[\/\+].*)/", unquote_plus(parse.path))
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://tv.expressen.se/%s/?standAlone=true&output=xml" % quote_plus(match.group(1))
        Expressen().get(options, url)

    elif re.findall("kanal5play", url):
        match = re.search(".*video/([0-9]+)", url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://www.kanal5play.se/api/getVideo?format=FLASH&videoId=%s" % match.group(1)
        Kanal5().get(options, url)


    elif re.findall("kanal9play", url):
        data = get_http_data(url)
        match = re.search("@videoPlayer\" value=\"(.*)\"", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        Kanal9().get(options, "c.brightcove.com")

    elif re.findall("dn.se", url):
        data = get_http_data(url)
        match = re.search("data-qbrick-mcid=\"([0-9A-F]+)\"", data)
        if not match:
            match = re.search("mediaId = \'([0-9A-F]+)\';", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            mcid = match.group(1) + "DE1BA107"
        else:
            mcid = match.group(1)
        host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/" + mcid
        data = get_http_data(host)
        xml = ET.XML(data)
        try:
            url = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            log.error("Can't find video file")
            sys.exit(2)
        Qbrick().get(options, url)

    elif re.findall("di.se", url):
        data = get_http_data(url)
        match = re.search("ccid: \"(.*)\"\,", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        host = "http://vms.api.qbrick.com/rest/v3/getplayer/" + match.group(1)
        data = get_http_data(host)
        xml = ET.XML(data)
        try:
            host = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            log.error("Can't find stream")
            sys.exit(2)
        Qbrick().get(options, host)

    elif re.findall("svd.se", url):
        match = re.search("_([0-9]+)\.svd", url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)

        data = get_http_data("http://www.svd.se/?service=ajax&type=webTvClip&articleId=" + match.group(1))
        match = re.search("mcid=([A-F0-9]+)\&width=", data)

        if not match:
            log.error("Can't find video file")
            sys.exit(2)

        host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/" + match.group(1)
        data = get_http_data(host)
        xml = ET.XML(data)
        try:
            host = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            log.error("Can't find video file")
            sys.exit(2)
        Qbrick().get(options, host)

    elif re.findall("urplay.se", url):
        Urplay().get(options, url)

    elif re.findall("sverigesradio", url):
        data = get_http_data(url)
        parse = urlparse(url)
        try:
            metafile = parse_qs(parse[4])["metafile"][0]
            other = "%s?%s" % (parse[2], parse[4])
        except KeyError:
            match = re.search("linkUrl=(.*)\;isButton=", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            other = unquote_plus(match.group(1))
        Sr().get(options, "http://sverigesradio.se")

    elif re.findall("svt.se", url):
        data = get_http_data(url)
        match = re.search("data-json-href=\"(.*)\"", data)
        if match:
            filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
            url = "http://www.svt.se%s" % filename
        else:
            log.error("Can't find video file")
            sys.exit(2)
        Svtplay().get(options, url)

    elif re.findall("svtplay.se", url):
        Svtplay().get(options, url)
    else:
        log.error("That site is not supported. Make a ticket or send a message")
        sys.exit(2)

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
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    setup_log(options.silent)

    url = args[0]
    get_media(url, options)

if __name__ == "__main__":
    main()
