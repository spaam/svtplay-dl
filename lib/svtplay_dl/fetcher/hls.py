# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import binascii
import copy
import os
import random
import re
import time
from datetime import datetime
from datetime import timedelta

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import modes
from svtplay_dl.error import ServiceError
from svtplay_dl.error import UIException
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.http import get_full_url
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import output
from svtplay_dl.utils.output import progress_stream
from svtplay_dl.utils.output import progressbar


class HLSException(UIException):
    def __init__(self, url, message):
        self.url = url
        super().__init__(message)


class LiveHLSException(HLSException):
    def __init__(self, url):
        super().__init__(url, "This is a live HLS stream, and they are not supported.")


def hlsparse(config, res, url, **kwargs):
    streams = {}

    if not res:
        return streams

    if res.status_code > 400:
        streams[0] = ServiceError(f"Can't read HLS playlist. {res.status_code}")
        return streams
    m3u8 = M3U8(res.text)

    keycookie = kwargs.pop("keycookie", None)
    authorization = kwargs.pop("authorization", None)
    httpobject = kwargs.pop("httpobject", None)
    output = kwargs.pop("output", None)
    channels = kwargs.pop("channels", None)
    codec = kwargs.pop("codec", "h264")
    media = {}
    subtitles = {}
    segments = None

    if m3u8.master_playlist:
        for i in m3u8.master_playlist:
            audio_url = None
            vcodec = None
            chans = None
            resolution = ""
            if i["TAG"] == "EXT-X-MEDIA":
                if "AUTOSELECT" in i and (i["AUTOSELECT"].upper() == "YES"):
                    if i["TYPE"] and i["TYPE"] != "SUBTITLES":
                        if "URI" in i:
                            if segments is None:
                                segments = True
                            if i["GROUP-ID"] not in media:
                                media[i["GROUP-ID"]] = []
                            if "CHANNELS" in i:
                                if i["CHANNELS"] == "6":
                                    chans = "51"
                            media[i["GROUP-ID"]].append([i["URI"], chans])
                        else:
                            segments = False
                if i["TYPE"] == "SUBTITLES":
                    if "URI" in i:
                        if i["GROUP-ID"] not in subtitles:
                            subtitles[i["GROUP-ID"]] = []
                        item = [i["URI"], i["LANGUAGE"]]
                        if item not in subtitles[i["GROUP-ID"]]:
                            subtitles[i["GROUP-ID"]].append(item)
                continue
            elif i["TAG"] == "EXT-X-STREAM-INF":
                if "AVERAGE-BANDWIDTH" in i:
                    bit_rate = float(i["AVERAGE-BANDWIDTH"]) / 1000
                else:
                    bit_rate = float(i["BANDWIDTH"]) / 1000
                if "RESOLUTION" in i:
                    resolution = i["RESOLUTION"]
                if "CODECS" in i:
                    if i["CODECS"][:3] == "hvc":
                        vcodec = "hevc"
                    if i["CODECS"][:3] == "avc":
                        vcodec = "h264"
                if "AUDIO" in i and (i["AUDIO"] in media):
                    chans = media[i["AUDIO"]][0][1]
                    audio_url = get_full_url(media[i["AUDIO"]][0][0], url)
                urls = get_full_url(i["URI"], url)
            else:
                continue  # Needs to be changed to utilise other tags.
            chans = chans if audio_url else channels
            codec = vcodec if vcodec else codec

            streams[int(bit_rate)] = HLS(
                copy.copy(config),
                urls,
                bit_rate,
                cookies=res.cookies,
                keycookie=keycookie,
                authorization=authorization,
                audio=audio_url,
                output=output,
                segments=bool(segments),
                channels=chans,
                codec=codec,
                resolution=resolution,
                **kwargs,
            )

        if subtitles and httpobject:
            for sub in list(subtitles.keys()):
                for n in subtitles[sub]:
                    m3u8s = M3U8(httpobject.request("get", get_full_url(n[0], url), cookies=res.cookies).text)
                    if "cmore" in url:
                        subtype = "wrstsegment"  # this have been seen in tv4play
                    else:
                        subtype = "wrst"
                    streams[int(random.randint(1, 40))] = subtitle(
                        copy.copy(config),
                        subtype,
                        get_full_url(m3u8s.media_segment[0]["URI"], url),
                        subfix=n[1],
                        output=copy.copy(output),
                        m3u8=m3u8s,
                    )

    elif m3u8.media_segment:
        config.set("segments", False)
        streams[0] = HLS(
            copy.copy(config),
            url,
            0,
            cookies=res.cookies,
            keycookie=keycookie,
            authorization=authorization,
            output=output,
            segments=False,
        )

    else:
        streams[0] = ServiceError("Can't find HLS playlist in m3u8 file.")

    return streams


class HLS(VideoRetriever):
    @property
    def name(self):
        return "hls"

    def download(self):
        self.output_extention = "ts"
        if self.segments:
            if self.audio and not self.config.get("only_video"):
                self._download(self.audio, file_name=(copy.copy(self.output), "audio.ts"))
            if not self.config.get("only_audio"):
                self._download(self.url, file_name=(self.output, "ts"))

        else:
            # Ignore audio
            self.audio = None
            self._download(self.url, file_name=(self.output, "ts"))

    def _download(self, url, file_name):
        cookies = self.kwargs.get("cookies", None)
        start_time = time.time()
        m3u8 = M3U8(self.http.request("get", url, cookies=cookies).text)
        key = None

        def random_iv():
            return os.urandom(16)

        file_d = output(file_name[0], self.config, file_name[1])
        if file_d is None:
            return

        if "EXT-X-MAP" in m3u8.media_segment[0]:
            entry = {"URI": get_full_url(m3u8.media_segment[0]["EXT-X-MAP"]["URI"], url), "EXTINF": {"duration": 0}}
            if "EXT-X-KEY" in m3u8.media_segment[0]:
                entry["EXT-X-KEY"] = {"URI": m3u8.media_segment[0]["EXT-X-KEY"]["URI"]}
            m3u8.media_segment.insert(0, entry)
        hls_time_stamp = self.kwargs.pop("hls_time_stamp", False)
        decryptor = None
        size_media = len(m3u8.media_segment)
        eta = ETA(size_media)
        total_duration = 0
        duration = 0
        max_duration = 0
        for index, i in enumerate(m3u8.media_segment):
            if "duration" in i["EXTINF"]:
                duration = i["EXTINF"]["duration"]
                max_duration = max(max_duration, duration)
                total_duration += duration
            item = get_full_url(i["URI"], url)

            if not self.config.get("silent"):
                if self.config.get("live"):
                    progressbar(size_media, index + 1, "".join(["DU: ", str(timedelta(seconds=int(total_duration)))]))
                else:
                    eta.increment()
                    progressbar(size_media, index + 1, "".join(["ETA: ", str(eta)]))

            data = self.http.request("get", item, cookies=cookies)
            if data.status_code == 404:
                break
            data = data.content

            if m3u8.encrypted:
                headers = {}
                if self.keycookie:
                    keycookies = self.keycookie
                else:
                    keycookies = cookies
                if self.authorization:
                    headers["authorization"] = self.authorization

                # Update key/decryptor
                if "EXT-X-KEY" in i:
                    keyurl = get_full_url(i["EXT-X-KEY"]["URI"], url)
                    if keyurl and keyurl[:4] == "skd:":
                        raise HLSException(keyurl, "Can't decrypt beacuse of DRM")
                    key = self.http.request("get", keyurl, cookies=keycookies, headers=headers).content
                    iv = binascii.unhexlify(i["EXT-X-KEY"]["IV"][2:].zfill(32)) if "IV" in i["EXT-X-KEY"] else random_iv()
                    backend = default_backend()
                    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
                    decryptor = cipher.decryptor()

                # In some cases the playlist say its encrypted but the files is not.
                # This happen on svtplay 5.1ch stream where it started with ID3..
                # Adding the other ones is header for mpeg-ts files. third byte is 10 or 11..
                if data[:3] != b"ID3" and data[:3] != b"\x47\x40\x11" and data[:3] != b"\x47\x40\x10" and data[4:12] != b"ftypisom":
                    if decryptor:
                        data = decryptor.update(data)
                    else:
                        raise ValueError("No decryptor found for encrypted hls steam.")
            file_d.write(data)

            if self.config.get("capture_time") > 0 and total_duration >= self.config.get("capture_time") * 60:
                break

            if (size_media == (index + 1)) and self.config.get("live"):
                sleep_int = (start_time + max_duration * 2) - time.time()
                if sleep_int > 0:
                    time.sleep(sleep_int)

                size_media_old = size_media
                while size_media_old == size_media:
                    start_time = time.time()

                    if hls_time_stamp:
                        end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=max_duration * 2)).replace(microsecond=0)
                        start_time_stamp = end_time_stamp - timedelta(minutes=1)

                        base_url = url.split(".m3u8")[0]
                        url = f"{base_url}.m3u8?in={start_time_stamp.isoformat()}&out={end_time_stamp.isoformat()}?"

                    new_m3u8 = M3U8(self.http.request("get", url, cookies=cookies).text)
                    for n_m3u in new_m3u8.media_segment:
                        if not any(d["URI"] == n_m3u["URI"] for d in m3u8.media_segment):
                            m3u8.media_segment.append(n_m3u)

                    size_media = len(m3u8.media_segment)

                    if size_media_old == size_media:
                        time.sleep(max_duration)

        file_d.close()
        if not self.config.get("silent"):
            progress_stream.write("\n")
        self.finished = True


class M3U8:
    # Created for hls version <=7
    # https://tools.ietf.org/html/rfc8216

    MEDIA_SEGMENT_TAGS = ("EXTINF", "EXT-X-BYTERANGE", "EXT-X-DISCONTINUITY", "EXT-X-KEY", "EXT-X-MAP", "EXT-X-PROGRAM-DATE-TIME", "EXT-X-DATERANGE")
    MEDIA_PLAYLIST_TAGS = (
        "EXT-X-TARGETDURATION",
        "EXT-X-MEDIA-SEQUENCE",
        "EXT-X-DISCONTINUITY-SEQUENCE",
        "EXT-X-ENDLIST",
        "EXT-X-PLAYLIST-TYPE",
        "EXT-X-I-FRAMES-ONLY",
    )
    MASTER_PLAYLIST_TAGS = ("EXT-X-MEDIA", "EXT-X-STREAM-INF", "EXT-X-I-FRAME-STREAM-INF", "EXT-X-SESSION-DATA", "EXT-X-SESSION-KEY")
    MEDIA_OR_MASTER_PLAYLIST_TAGS = ("EXT-X-INDEPENDENT-SEGMENTS", "EXT-X-START")

    TAG_TYPES = {"MEDIA_SEGMENT": 0, "MEDIA_PLAYLIST": 1, "MASTER_PLAYLIST": 2}

    def __init__(self, data):

        self.version = None

        self.media_segment = []
        self.media_playlist = {}
        self.master_playlist = []

        self.encrypted = False
        self.independent_segments = False

        self.parse_m3u(data)

    def __str__(self):
        return "Version: {}\nMedia Segment: {}\nMedia Playlist: {}\nMaster Playlist: {}\nEncrypted: {}\tIndependent_segments: {}".format(
            self.version,
            self.media_segment,
            self.media_playlist,
            self.master_playlist,
            self.encrypted,
            self.independent_segments,
        )

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
                        info["URI"] = lines[index + 1]

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
                        self.independent_segments = True

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
        search_line = re.search(r"^([A-Z\-]*):(.*)", line)
        return search_line.group(1), search_line.group(2)
    except Exception:
        return line, None


def _get_tuple_attribute(attribute):
    attr_tuple = {}
    for art_l in re.split(""",(?=(?:[^'"]|'[^']*'|"[^"]*")*$)""", attribute):
        if art_l:
            name, value = art_l.split("=", 1)
            name = name.strip()
            # Checks for attribute name
            if not re.match(r"^[A-Z0-9\-]*$", name):
                raise ValueError("Not a valid attribute name.")

            # Remove extra quotes of string
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            attr_tuple[name] = value

    return attr_tuple
