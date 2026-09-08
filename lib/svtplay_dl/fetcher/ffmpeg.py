import logging
import os
import subprocess
from shutil import which

from svtplay_dl.error import UIException
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.fetcher.json_to_m3u8 import m3u8_to_file
from svtplay_dl.fetcher.m3u8 import M3U8
from svtplay_dl.utils.fetcher import filter_files
from svtplay_dl.utils.output import ETA
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.output import progress_stream
from svtplay_dl.utils.output import progressbar


def _parse_out_time(value):
    # ffmpeg -progress reports out_time as "HH:MM:SS.ffffff"
    try:
        h, m, s = value.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except ValueError:
        return 0.0


class FFMPEGException(UIException):
    def __init__(self, url, message):
        self.url = url
        super().__init__(message)


class LiveFFMPEGException(FFMPEGException):
    def __init__(self, url):
        super().__init__(url, "This is a live stream, and they are not supported.")


class FFMPEG(VideoRetriever):
    @property
    def name(self):
        return "hls"  # ffmpeg hack to workaround

    def download(self):
        self.output_extention = "ts"
        playlist_file_audio = None
        cookies = self.kwargs.get("cookies", None)

        self.output_extention = "mp4"
        if self.config.get("live") and not self.config.get("force"):
            raise LiveFFMPEGException(self.url)

        detect = which("ffmpeg")
        if detect is None:
            logging.error("Cant detect ffmpeg. Cant download using this method without it.")
            return

        m3u8 = M3U8(self.http.request("get", self.url, cookies=cookies).text)

        m3u8 = filter_files(m3u8)
        total_duration = sum(seg["EXTINF"]["duration"] for seg in m3u8.media_segment if "EXTINF" in seg)
        filename = formatname(self.output, self.config)
        playlist_file = filename.with_suffix(".m3u8")
        m3u8_to_file(m3u8, playlist_file)
        if self.audio:
            m3u8 = M3U8(self.http.request("get", self.audio, cookies=cookies).text)
            m3u8 = filter_files(m3u8)
            playlist_file_audio = filename.with_suffix(".audio.m3u8")
            m3u8_to_file(m3u8, playlist_file_audio)

        protocol_whitelist = [
            "-protocol_whitelist",
            "file,http,https,tcp,tls,crypto",
            "-allowed_extensions",
            "ALL",
        ]
        cmd = [detect, "-y", *protocol_whitelist, "-i", str(playlist_file)]
        if self.audio:
            cmd += [*protocol_whitelist, "-i", str(playlist_file_audio)]
        cmd += [
            "-c",
            "copy",
            "-progress",
            "pipe:1",
            "-nostats",
            "-loglevel",
            "error",
            str(filename),
        ]

        returncode = self._run_with_progress(cmd, total_duration)
        if returncode == 0:
            self.finished = True
            self.audio = None
        if os.path.isfile(playlist_file):
            os.remove(playlist_file)
        if os.path.isfile(playlist_file_audio):
            os.remove(playlist_file_audio)

    def _run_with_progress(self, cmd, total_duration):
        eta = ETA(int(total_duration)) if total_duration else None
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        out_time = 0.0
        for line in process.stdout:
            key, _, value = line.strip().partition("=")
            if key == "out_time":
                out_time = _parse_out_time(value)

            if not self.config.get("silent") and total_duration:
                pos = min(int(out_time), int(total_duration))
                msg = ""
                if eta:
                    eta.update(pos)
                    msg = f"ETA: {eta}"
                progressbar(int(total_duration), pos, msg)

        process.wait()
        if not self.config.get("silent"):
            progress_stream.write("\n")

        stderr = process.stderr.read()
        if process.returncode != 0:
            logging.error("Something went wrong: %s", stderr.strip())
        return process.returncode
