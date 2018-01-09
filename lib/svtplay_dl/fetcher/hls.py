# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import os
import re
import copy
import time
import datetime

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
    m3u8 = M3U8(res.text)
    http = HTTP(options)
    keycookie = kwargs.pop("keycookie", None)

    media = {}
    for i in m3u8.master_playlist:
        audio_url = None
        if i["TAG"] == "EXT-X-MEDIA":
            if "DEFAULT" in i and (i["DEFAULT"].upper() == "YES"):
                if i["TYPE"] and ("URI" in i):
                    if i["GROUP-ID"] not in media:
                        media[i["GROUP-ID"]] = []
                    media[i["GROUP-ID"]].append(i["URI"])
            continue
        elif i["TAG"] == "EXT-X-STREAM-INF":
            bit_rate = float(i["BANDWIDTH"]) / 1000

            if "AUDIO" in i and (i["AUDIO"] in media):
                audio_url = media[i["AUDIO"]][0]

            urls = _get_full_url(i["URI"], url)
        else:
            continue # Needs to be changed to utilise other tags.
        res2 = http.get(urls, cookies=res.cookies)
        if res2.status_code < 400:

            streams[int(bit_rate)] = HLS(copy.copy(options), urls, bit_rate, cookies=res.cookies, keycookie=keycookie, audio=audio_url)
    return streams


class HLS(VideoRetriever):
    def name(self):
        return "hls"

    def download(self):

        if self.audio:
            if self.options.live:
                raise LiveHLSException(self.url)

            cookies = self.kwargs["cookies"]
            audio_data_m3u = self.http.request("get", self.audio, cookies=cookies).text
            audio_m3u8 = M3U8(audio_data_m3u)
            total_size = audio_m3u8.media_segment[-1]["EXT-X-BYTERANGE"]["n"] + audio_m3u8.media_segment[-1]["EXT-X-BYTERANGE"]["o"]
            self._download_url(audio_m3u8.media_segment[0]["URI"], audio=True, total_size=total_size)

            data_m3u = self.http.request("get", self.url, cookies=cookies).text
            m3u8 = M3U8(data_m3u)
            total_size = m3u8.media_segment[-1]["EXT-X-BYTERANGE"]["n"] + m3u8.media_segment[-1]["EXT-X-BYTERANGE"]["o"]
            self._download_url(m3u8.media_segment[0]["URI"], total_size=total_size)
        else:
            self._download()

    def _download(self):
        cookies = self.kwargs["cookies"]
        start_time = time.time()
        m3u8 = M3U8(self.http.request("get", self.url, cookies=cookies).text)
        key = None

        if m3u8.encrypted:
            try:
                from Crypto.Cipher import AES
            except ImportError:
                log.error("You need to install pycrypto to download encrypted HLS streams")
                sys.exit(2)

        file_d = output(self.options, "ts")
        if file_d is None:
            return

        decryptor = None
        size_media = len(m3u8.media_segment)
        eta = ETA(size_media)
        duration = 0
        for index, i in enumerate(m3u8.media_segment):
            if "duration" in i["EXTINF"]:
                duration += i["EXTINF"]["duration"]
            item = _get_full_url(i["URI"], self.url)

            if not self.options.silent:
                if self.options.live:
                    progressbar(size_media, index + 1, ''.join(['DU: ', str(datetime.timedelta(seconds=int(duration)))]))
                else:
                    eta.increment()
                    progressbar(size_media, index + 1, ''.join(['ETA: ', str(eta)]))

            data = self.http.request("get", item, cookies=cookies)
            if data.status_code == 404:
                break
            data = data.content
            if m3u8.encrypted:
                if self.keycookie:
                    keycookies = self.keycookie
                else:
                    keycookies = cookies

                # Update key/decryptor
                if "EXT-X-KEY" in i:
                    keyurl = _get_full_url(i["EXT-X-KEY"]["URI"], self.url)
                    key = self.http.request("get", keyurl, cookies=keycookies).content
                    decryptor = AES.new(key, AES.MODE_CBC, os.urandom(16))

                if decryptor:
                    data = decryptor.decrypt(data)
                else:
                    raise ValueError("No decryptor found for encrypted hls steam.")

            file_d.write(data)

            if (self.options.capture_time > 0) and duration >= (self.options.capture_time * 60):
                break

            if (size_media == (index + 1)) and self.options.live:
                while (start_time + i["EXTINF"]["duration"] * 2) >= time.time():
                    time.sleep(1.0)

                start_time = time.time()
                new_m3u8 = M3U8(self.http.request("get", self.url, cookies=cookies).text)
                for n_m3u in new_m3u8.media_segment:
                    if n_m3u not in m3u8.media_segment:
                        m3u8.media_segment.append(n_m3u)

                size_media = len(m3u8.media_segment)

        file_d.close()
        if not self.options.silent:
            progress_stream.write('\n')
        self.finished = True

class M3U8():
    # Created for hls version <=7
    # https://tools.ietf.org/html/rfc8216

    MEDIA_SEGMENT_TAGS = ("EXTINF", "EXT-X-BYTERANGE", "EXT-X-DISCONTINUITY",
                          "EXT-X-KEY", "EXT-X-MAP", "EXT-X-PROGRAM-DATE-TIME", "EXT-X-DATERANGE")
    MEDIA_PLAYLIST_TAGS = ("EXT-X-TARGETDURATION", "EXT-X-MEDIA-SEQUENCE", "EXT-X-DISCONTINUITY-SEQUENCE",
                           "EXT-X-ENDLIST", "EXT-X-PLAYLIST-TYPE", "EXT-X-I-FRAMES-ONLY")
    MASTER_PLAYLIST_TAGS = ("EXT-X-MEDIA", "EXT-X-STREAM-INF", "EXT-X-I-FRAME-STREAM-INF",
                            "EXT-X-SESSION-DATA", "EXT-X-SESSION-KEY")
    MEDIA_OR_MASTER_PLAYLIST_TAGS = ("EXT-X-INDEPENDENT-SEGMENTS", "EXT-X-START")

    TAG_TYPES = {"MEDIA_SEGMENT": 0, "MEDIA_PLAYLIST": 1, "MASTER_PLAYLIST": 2}

    def __init__(self, data):

        self.version = None

        self.media_segment = []
        self.media_playlist = {}
        self.master_playlist = []

        self.encrypted = False

        self.parse_m3u(data)

    def __str__(self):
        return "Version: {0}\nMedia Segment: {1}\nMedia Playlist: {2}\nMaster Playlist: {3}\nEncrypted: {4}"\
            .format(self.version, self.media_segment, self.media_playlist, self.master_playlist, self.encrypted)

    def parse_m3u(self, data):
        if not data.startswith("#EXTM3U"):
            raise ValueError("Does not appear to be an 'EXTM3U' file.")

        data = data.replace("\r\n", "\n")
        lines = data.split("\n")[1:]

        last_tag_type = None
        tag_type = None

        media_segment_info = {}

        for index, l in enumerate(lines):
            if not l:
                continue
            elif l.startswith("#EXT"):

                info = {}
                tag, attr = _get_tag_attribute(l)
                if tag == "EXT-X-VERSION":
                    self.version = int(attr)

                # 4.3.2.  Media Segment Tags
                elif tag in M3U8.MEDIA_SEGMENT_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_SEGMENT"]
                    # 4.3.2.1.  EXTINF
                    if tag == "EXTINF":
                        if "," in attr:
                            dur, title = attr.split(",", 1)
                        else:
                            dur = attr
                            title = None
                        info["duration"] = float(dur)
                        info["title"] = title

                    # 4.3.2.2.  EXT-X-BYTERANGE
                    elif tag == "EXT-X-BYTERANGE":
                        if "@" in attr:
                            n, o = attr.split("@", 1)
                            info["n"], info["o"] = (int(n), int(o))
                        else:
                            info["n"] = int(attr)
                            info["o"] = 0

                    # 4.3.2.3.  EXT-X-DISCONTINUITY
                    elif tag == "EXT-X-DISCONTINUITY":
                        pass

                    # 4.3.2.4.  EXT-X-KEY
                    elif tag == "EXT-X-KEY":
                        self.encrypted = True
                        info = _get_tuple_attribute(attr)

                    # 4.3.2.5.  EXT-X-MAP
                    elif tag == "EXT-X-MAP":
                        info = _get_tuple_attribute(attr)

                    # 4.3.2.6.  EXT-X-PROGRAM-DATE-TIME"
                    elif tag == "EXT-X-PROGRAM-DATE-TIME":
                        info = attr

                    # 4.3.2.7.  EXT-X-DATERANGE
                    elif tag == "EXT-X-DATERANGE":
                        info = _get_tuple_attribute(attr)

                    media_segment_info[tag] = info

                # 4.3.3.  Media Playlist Tags
                elif tag in M3U8.MEDIA_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_PLAYLIST"]
                    # 4.3.3.1.  EXT-X-TARGETDURATION
                    if tag == "EXT-X-TARGETDURATION":
                        info = int(attr)

                    # 4.3.3.2.  EXT-X-MEDIA-SEQUENCE
                    elif tag == "EXT-X-MEDIA-SEQUENCE":
                        info = int(attr)

                    # 4.3.3.3.  EXT-X-DISCONTINUITY-SEQUENCE
                    elif tag == "EXT-X-DISCONTINUITY-SEQUENCE":
                        info = int(attr)

                    # 4.3.3.4.  EXT-X-ENDLIST
                    elif tag == "EXT-X-ENDLIST":
                        break

                    # 4.3.3.5.  EXT-X-PLAYLIST-TYPE
                    elif tag == "EXT-X-PLAYLIST-TYPE":
                        info = attr

                    # 4.3.3.6.  EXT-X-I-FRAMES-ONLY
                    elif tag == "EXT-X-I-FRAMES-ONLY":
                        pass

                    self.media_playlist[tag] = info

                # 4.3.4. Master Playlist Tags
                elif tag in M3U8.MASTER_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MASTER_PLAYLIST"]
                    # 4.3.4.1.  EXT-X-MEDIA
                    if tag == "EXT-X-MEDIA":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.2.  EXT-X-STREAM-INF
                    elif tag == "EXT-X-STREAM-INF":
                        info = _get_tuple_attribute(attr)
                        if "BANDWIDTH" not in info:
                            raise ValueError("Can't find 'BANDWIDTH' in 'EXT-X-STREAM-INF'")
                        info["URI"] = lines[index+1]

                    # 4.3.4.3.  EXT-X-I-FRAME-STREAM-INF
                    elif tag == "EXT-X-I-FRAME-STREAM-INF":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.4.  EXT-X-SESSION-DATA
                    elif tag == "EXT-X-SESSION-DATA":
                        info = _get_tuple_attribute(attr)

                    # 4.3.4.5.  EXT-X-SESSION-KEY
                    elif tag == "EXT-X-SESSION-KEY":
                        self.encrypted = True
                        info = _get_tuple_attribute(attr)
                    info["TAG"] = tag

                    self.master_playlist.append(info)

                # 4.3.5. Media or Master Playlist Tags
                elif tag in M3U8.MEDIA_OR_MASTER_PLAYLIST_TAGS:

                    tag_type = M3U8.TAG_TYPES["MEDIA_PLAYLIST"]
                    # 4.3.5.1. EXT-X-INDEPENDENT-SEGMENTS
                    if tag == "EXT-X-INDEPENDENT-SEGMENTS":
                        pass

                    # 4.3.5.2. EXT-X-START
                    elif tag == "EXT-X-START":
                        info = _get_tuple_attribute(attr)

                    self.media_playlist[tag] = info

                # Unused tags
                else:
                    pass
            # This is a comment
            elif l.startswith("#"):
                pass
            # This must be a url/uri
            else:
                tag_type = None

                if last_tag_type is M3U8.TAG_TYPES["MEDIA_SEGMENT"]:
                    media_segment_info["URI"] = l
                    self.media_segment.append(media_segment_info)
                    media_segment_info = {}

            last_tag_type = tag_type

            if self.media_segment and self.master_playlist:
                raise ValueError("This 'M3U8' file contains data for both 'Media Segment' and 'Master Playlist'. This is not allowed.")


def _get_tag_attribute(line):
    line = line[1:]
    try:
        search_line = re.search("^([A-Z\-]*):(.*)", line)
        return search_line.group(1), search_line.group(2)
    except:
        return line, None


def _get_tuple_attribute(attribute):
    attr_tuple = {}
    for art_l in re.split(''',(?=(?:[^'"]|'[^']*'|"[^"]*")*$)''', attribute):
        if art_l:
            name, value = art_l.split("=", 1)
            name = name.strip()
            # Checks for attribute name
            if not re.match("^[A-Z0-9\-]*$", name):
                raise ValueError("Not a valid attribute name.")

            # Remove extra quotes of string
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            attr_tuple[name] = value

    return attr_tuple
