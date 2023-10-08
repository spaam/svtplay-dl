# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import binascii
import copy
import os
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
from svtplay_dl.fetcher.m3u8 import M3U8
from svtplay_dl.subtitle import subtitle_probe
from svtplay_dl.utils.fetcher import filter_files
from svtplay_dl.utils.http import get_full_url
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.output import progress_stream
from svtplay_dl.utils.output import progressbar


class HLSException(UIException):
    def __init__(self, url, message):
        self.url = url
        super().__init__(message)


class LiveHLSException(HLSException):
    def __init__(self, url):
        super().__init__(url, "This is a live HLS stream, and they are not supported.")


def hlsparse(config, res, url, output, **kwargs):
    if not res:
        return

    if res.status_code > 400:
        yield ServiceError(f"Can't read HLS playlist. {res.status_code}")
        return

    yield from _hlsparse(config, res.text, url, output, cookies=res.cookies, **kwargs)


def _hlsparse(config, text, url, output, **kwargs):
    m3u8 = M3U8(text)
    keycookie = kwargs.pop("keycookie", None)
    cookies = kwargs.pop("cookies", None)
    authorization = kwargs.pop("authorization", None)
    loutput = copy.copy(output)
    loutput["ext"] = "ts"
    channels = kwargs.pop("channels", None)
    codec = kwargs.pop("codec", "h264")
    media = {}
    subtitles = {}
    videos = {}
    segments = None

    if m3u8.master_playlist:
        for i in m3u8.master_playlist:
            audio_url = None
            vcodec = None
            chans = None
            audio_group = None
            language = ""
            resolution = ""
            if i["TAG"] == "EXT-X-MEDIA":
                if i["TYPE"] and i["TYPE"] != "SUBTITLES":
                    if "URI" in i:
                        if segments is None:
                            segments = True
                        if i["GROUP-ID"] not in media:
                            media[i["GROUP-ID"]] = []
                        if "CHANNELS" in i:
                            if i["CHANNELS"] == "6":
                                chans = "51"
                        if "LANGUAGE" in i:
                            language = i["LANGUAGE"]
                        if "AUTOSELECT" in i and i["AUTOSELECT"].upper() == "YES":
                            role = "main"
                        else:
                            role = "alt"
                        media[i["GROUP-ID"]].append([i["URI"], chans, language, role])
                    else:
                        segments = False
                if i["TYPE"] == "SUBTITLES":
                    if "URI" in i:
                        caption = None
                        if i["GROUP-ID"] not in subtitles:
                            subtitles[i["GROUP-ID"]] = []
                        if "LANGUAGE" in i:
                            lang = i["LANGUAGE"]
                        else:
                            lang = "und"
                        if "CHARACTERISTICS" in i:
                            caption = True
                        item = [i["URI"], lang, caption]
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
                if "AUDIO" in i:
                    audio_group = i["AUDIO"]
                urls = get_full_url(i["URI"], url)
                videos[bit_rate] = [urls, resolution, vcodec, audio_group]
            else:
                continue  # Needs to be changed to utilise other tags.

        for bit_rate in list(videos.keys()):
            urls, resolution, vcodec, audio_group = videos[bit_rate]
            if audio_group and media:
                for group in media[audio_group]:
                    audio_url = get_full_url(group[0], url)
                    chans = group[1] if audio_url else channels
                    codec = vcodec if vcodec else codec

                    yield HLS(
                        copy.copy(config),
                        urls,
                        bit_rate,
                        cookies=cookies,
                        keycookie=keycookie,
                        authorization=authorization,
                        audio=audio_url,
                        output=loutput,
                        segments=bool(segments),
                        channels=chans,
                        codec=codec,
                        resolution=resolution,
                        language=group[2],
                        role=group[3],
                        **kwargs,
                    )
            else:
                chans = channels
                codec = vcodec if vcodec else codec
                yield HLS(
                    copy.copy(config),
                    urls,
                    bit_rate,
                    cookies=cookies,
                    keycookie=keycookie,
                    authorization=authorization,
                    audio=audio_url,
                    output=loutput,
                    segments=bool(segments),
                    channels=chans,
                    codec=codec,
                    resolution=resolution,
                    **kwargs,
                )

        if subtitles:
            for sub in list(subtitles.keys()):
                for n in subtitles[sub]:
                    subfix = n[2]
                    if len(subtitles[sub]) > 1:
                        if subfix:
                            subfix = f"{n[1]}-caption"
                    yield from subtitle_probe(
                        copy.copy(config), get_full_url(n[0], url), output=copy.copy(output), subfix=subfix, cookies=cookies, **kwargs
                    )

    elif m3u8.media_segment:
        config.set("segments", False)
        yield HLS(
            copy.copy(config),
            url,
            0,
            cookies=cookies,
            keycookie=keycookie,
            authorization=authorization,
            output=loutput,
            segments=False,
        )
    else:
        yield ServiceError("Can't find HLS playlist in m3u8 file.")


class HLS(VideoRetriever):
    @property
    def name(self):
        return "hls"

    def download(self):
        self.output_extention = "ts"
        if self.segments:
            if self.audio and not self.config.get("only_video"):
                # self._download(self.audio, file_name=(copy.copy(self.output), "audio.ts"))
                self._download(self.audio, True)
            if not self.audio or not self.config.get("only_audio"):
                self._download(self.url)

        else:
            # Ignore audio
            self.audio = None
            self._download(self.url)

    def _download(self, url, audio=False):
        cookies = self.kwargs.get("cookies", None)
        start_time = time.time()
        m3u8 = M3U8(self.http.request("get", url, cookies=cookies).text)
        key = None

        def random_iv():
            return os.urandom(16)

        if audio:
            self.output["ext"] = "audio.ts"
        else:
            self.output["ext"] = "ts"
        filename = formatname(self.output, self.config)
        file_d = open(filename, "wb")

        hls_time_stamp = self.kwargs.pop("hls_time_stamp", False)
        if self.kwargs.get("filter", False):
            m3u8 = filter_files(m3u8)
        decryptor = None
        size_media = len(m3u8.media_segment)
        eta = ETA(size_media)
        total_duration = 0
        duration = 0
        max_duration = 0
        for index, i in enumerate(m3u8.media_segment):
            if "EXTINF" in i and "duration" in i["EXTINF"]:
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

            headers = {}
            if "EXT-X-BYTERANGE" in i:
                headers["Range"] = f'bytes={i["EXT-X-BYTERANGE"]["o"]}-{i["EXT-X-BYTERANGE"]["o"] + i["EXT-X-BYTERANGE"]["n"] - 1}'
            data = self.http.request("get", item, cookies=cookies, headers=headers)
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
