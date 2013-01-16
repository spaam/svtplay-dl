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
import shlex
import json
import time
import logging

from svtplay.log import log
from svtplay.utils import get_http_data, select_quality

from svtplay.service.aftonbladet import Aftonbladet
from svtplay.service.dr import Dr
from svtplay.service.expressen import Expressen
from svtplay.service.hbo import Hbo
from svtplay.service.justin import Justin
from svtplay.service.kanal5 import Kanal5
from svtplay.service.kanal9 import Kanal9
from svtplay.service.nrk import Nrk
from svtplay.service.qbrick import Qbrick
from svtplay.service.ruv import Ruv
from svtplay.service.sr import Sr
from svtplay.service.svtplay import Svtplay
from svtplay.service.tv4play import Tv4play
from svtplay.service.urplay import Urplay
from svtplay.service.viaplay import Viaplay

__version__ = "0.8.2013.01.15"

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

def progress(byte, total, extra = ""):
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
    progress_stream.write(progresstr + ' ' + extra + '\r')

    if byte >= total:
        progress_stream.write('\n')

    progress_stream.flush()

def download_hls(options, url, baseurl=None):
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
    total_size = response.info()['Content-Length']
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
                options.output = "%s%s" % (options.output, extension.group(1))
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

def get_media(url, options):
    sites = [Aftonbladet(), Dr(), Expressen(), Hbo(), Justin(), Kanal5(), Kanal9(),
             Nrk(), Qbrick(), Ruv(), Sr(), Svtplay(), Tv4play(), Urplay(), Viaplay()]
    stream = None
    for i in sites:
        if i.handle(url):
            stream = i
            break
    if not stream:
        log.error("That site is not supported. Make a ticket or send a message")
        sys.exit(2)

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
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    setup_log(options.silent)

    url = args[0]
    get_media(url, options)

if __name__ == "__main__":
    main()
