# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import os
import re

from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.output import progressbar, progress_stream, ETA
from svtplay_dl.log import log

def download_hls(options, url, baseurl=None):
    data = get_http_data(url)
    globaldata, files = parsem3u(data)
    streams = {}
    for i in files:
        streams[int(i[1]["BANDWIDTH"])] = i[0]

    test = select_quality(options, streams)
    if baseurl and test[:4] != 'http':
        test = "%s/%s" % (baseurl, test)
    m3u8 = get_http_data(test)
    globaldata, files = parsem3u(m3u8)
    encrypted = False
    key = None
    try:
        keydata = globaldata["KEY"]
        encrypted = True
    except KeyError:
        pass

    if encrypted:
        try:
            from Crypto.Cipher import AES
        except ImportError:
            log.error("You need to install pycrypto to download encrypted HLS streams")
            sys.exit(2)

        match = re.search(r'URI="(https?://.*?)"', keydata)
        key = get_http_data(match.group(1))
        rand = os.urandom(16)
        decryptor = AES.new(key, AES.MODE_CBC, rand)
    if options.output != "-":
        extension = re.search(r"(\.[a-z0-9]+)$", options.output)
        if not extension:
            options.output = "%s.ts" % options.output
        log.info("Outfile: %s", options.output)
        file_d = open(options.output, "wb")
    else:
        file_d = sys.stdout

    n = 0
    eta = ETA(len(files))
    for i in files:
        item = i[0]
        if options.output != "-":
            eta.increment()
            progressbar(len(files), n, ''.join(['ETA: ', str(eta)]))
            n += 1
        if item[0:5] != "http:":
            item = "%s/%s" % (baseurl, item)
        data = get_http_data(item)
        if encrypted:
            data = decryptor.decrypt(data)
        file_d.write(data)

    if options.output != "-":
        file_d.close()
        progress_stream.write('\n')

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
            for i in range(0, len(info)):
                if info[i][0] == "BANDWIDTH":
                    streaminfo.update({info[i][0]: info[i][1]})
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

