# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import os
import re
import copy

from svtplay_dl.output import progressbar, progress_stream, ETA, output
from svtplay_dl.log import log
from svtplay_dl.error import UIException, ServiceError
from svtplay_dl.fetcher import VideoRetriever


class HLSException(UIException):
    def __init__(self, url, message):
        self.url = url
        super(HLSException, self).__init__(message)


class LiveHLSException(HLSException):
    def __init__(self, url):
        super(LiveHLSException, self).__init__(
            url, "This is a live HLS stream, and they are not supported.")


def _get_full_url(url, srcurl):
    if url[:4] == 'http':
        return url
    if url[0] == '/':
        baseurl = re.search(r'^(http[s]{0,1}://[^/]+)/', srcurl)
        return "%s%s" % (baseurl.group(1), url)

    # remove everything after last / in the path of the URL
    baseurl = re.sub(r'^([^\?]+)/[^/]*(\?.*)?$', r'\1', srcurl)
    returl = "%s/%s" % (baseurl, url)

    return returl


def hlsparse(options, res, url):
    streams = {}

    if not res:
        return None

    if res.status_code > 400:
        streams[0] = ServiceError("Can't read HLS playlist. {0}".format(res.status_code))
        return streams
    files = (parsem3u(res.text))[1]

    for i in files:
        try:
            bitrate = float(i[1]["BANDWIDTH"])/1000
        except KeyError:
            streams[0] = ServiceError("Can't read HLS playlist")
            return streams
        streams[int(bitrate)] = HLS(copy.copy(options), _get_full_url(i[0], url), bitrate, cookies=res.cookies)
    return streams


class HLS(VideoRetriever):
    def name(self):
        return "hls"

    def download(self):
        if self.options.live and not self.options.force:
            raise LiveHLSException(self.url)

        cookies = self.kwargs["cookies"]
        m3u8 = self.http.request("get", self.url, cookies=cookies).text
        globaldata, files = parsem3u(m3u8)
        encrypted = False
        key = None
        if "KEY" in globaldata:
            keydata = globaldata["KEY"]
            encrypted = True

        if encrypted:
            try:
                from Crypto.Cipher import AES
            except ImportError:
                log.error("You need to install pycrypto to download encrypted HLS streams")
                sys.exit(2)

            match = re.search(r'URI="(https?://.*?)"', keydata)
            key = self.http.request("get", match.group(1)).content
            rand = os.urandom(16)
            decryptor = AES.new(key, AES.MODE_CBC, rand)

        file_d = output(self.options, "ts")
        if hasattr(file_d, "read") is False:
            return

        n = 1
        eta = ETA(len(files))
        for i in files:
            item = _get_full_url(i[0], self.url)

            if self.options.output != "-" and not self.options.silent:
                eta.increment()
                progressbar(len(files), n, ''.join(['ETA: ', str(eta)]))
                n += 1

            data = self.http.request("get", item, cookies=cookies)
            if data.status_code == 404:
                break
            data = data.content
            if encrypted:
                data = decryptor.decrypt(data)
            file_d.write(data)

        if self.options.output != "-":
            file_d.close()
            if not self.options.silent:
                progress_stream.write('\n')
            self.finished = True


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
            # not a proper parser
            info = [x.strip().split("=", 1) for x in l[18:].split(",")]
            for i in range(0, len(info)):
                if info[i][0] == "BANDWIDTH":
                    streaminfo.update({info[i][0]: info[i][1]})
                if info[i][0] == "RESOLUTION":
                    streaminfo.update({info[i][0]: info[i][1]})
        elif l.startswith("#EXT-X-ENDLIST"):
            break
        elif l.startswith("#EXT-X-"):
            line = [l[7:].strip().split(":", 1)]
            if len(line[0]) == 1:
                line[0].append("None")
            globdata.update(dict(line))
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

