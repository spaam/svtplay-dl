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
from svtplay_dl.utils import HTTP


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
        return "{0}{1}".format(baseurl.group(1), url)

    # remove everything after last / in the path of the URL
    baseurl = re.sub(r'^([^\?]+)/[^/]*(\?.*)?$', r'\1', srcurl)
    returl = "{0}/{1}".format(baseurl, url)

    return returl


def hlsparse(options, res, url, **kwargs):
    streams = {}

    if not res:
        return None

    if res.status_code > 400:
        streams[0] = ServiceError("Can't read HLS playlist. {0}".format(res.status_code))
        return streams
    m3u8 = M3U8()
    files = (m3u8.parse_m3u(res.text))[1]
    print(m3u8) # TODO: rm
    http = HTTP(options)
    keycookie = kwargs.pop("keycookie", None)
    
    for i in files:
        try:
            bitrate = float(i[1]["BANDWIDTH"])/1000
        except KeyError:
            streams[0] = ServiceError("Can't read HLS playlist")
            return streams
        urls = _get_full_url(i[0], url)
        res2 = http.get(urls, cookies=res.cookies)
        if res2.status_code < 400:
            streams[int(bitrate)] = HLS(copy.copy(options), urls, bitrate, cookies=res.cookies, keycookie=keycookie)
    return streams


class HLS(VideoRetriever):
    def name(self):
        return "hls"

    def download(self):
        if self.options.live and not self.options.force:
            raise LiveHLSException(self.url)

        cookies = self.kwargs["cookies"]
        m3u8 = M3U8()
        data_m3u = self.http.request("get", self.url, cookies=cookies).text
        globaldata, files = m3u8.parse_m3u(data_m3u)
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
            if not match:
                match = re.search(r'URI="([^"]+)"', keydata)
            keyurl = _get_full_url(match.group(1), self.url)
            if self.keycookie:
                keycookies = self.keycookie
            else:
                keycookies = cookies
            key = self.http.request("get", keyurl, cookies=keycookies).content
            rand = os.urandom(16)
            decryptor = AES.new(key, AES.MODE_CBC, rand)

        file_d = output(self.options, "ts")
        if file_d is None:
            return

        n = 1
        eta = ETA(len(files))
        for i in files:
            item = _get_full_url(i[0], self.url)

            if not self.options.silent:
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

        file_d.close()
        if not self.options.silent:
            progress_stream.write('\n')
        self.finished = True

class M3U8():

    def __init__(self):

        self.files = []
        self.glob_data = {}
        self.version = None
        self.target_duration = None

    def __str__(self):
        return "Files: {0}\nGlobData: {1}\nVersion: {2}\nTargetDuration: {3}"\
            .format(self.files, self.glob_data, self.version, self.target_duration)

    def parse_m3u(self, data):
        if not re.search("^#EXTM3U", data):
            raise ValueError("Does not appear to be an 'EXTM3U' file.")

        lines = []
        data = data.replace("\r\n", "\n")
        lines = data.split("\n")[1:]
        self.steam_info = ""

        for index, l in enumerate(lines):
            if l and l.startswith("#EXT"):
                stream_info = {}
                if l.startswith("#EXT-X-VERSION:"):
                    self.version = int(re.search("^#EXT-X-VERSION:(.*)", l).group(1))
                elif l.startswith("#EXT-X-TARGETDURATION:"):
                    self.target_duration = float(re.search("^#EXT-X-TARGETDURATION:(.*)", l).group(1))
                elif l.startswith("#EXT-X-STREAM-INF:"):
                    attribute = re.search("^#EXT-X-STREAM-INF:(.*)", l).group(1)

                    for art_l in re.split(''',(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', attribute):
                        if art_l:
                            art_l_s = art_l.split("=")
                            stream_info[art_l_s[0]] = art_l_s[1]

                    self.files.append((lines[index + 1], stream_info))

                elif l.startswith("#EXT-X-MAP:"):
                    line = l[11:]
                    if line.startswith("URI"):
                        self.files.append((line[5:].split("\"")[0], stream_info))
                        self.files.append((lines[index + 1], stream_info))
                elif l.startswith("#EXTINF:"):
                    try:
                        dur, title = l[8:].strip().split(",", 1)
                    except:
                        dur = l[8:].strip()
                        title = None
                    stream_info['duration'] = dur
                    stream_info['title'] = title
                    self.files.append((lines[index + 1], stream_info))
                elif l.startswith("#EXT-X-ENDLIST") or l.startswith("#EXT-X-BYTERANGE:"):
                    break

        return self.glob_data, self.files
