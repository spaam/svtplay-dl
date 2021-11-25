import logging
import os
import pathlib
import platform
import re
import sys
from json import dumps
from random import sample
from shutil import which

from requests import codes
from requests import post
from requests import Timeout
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.proc import run_program
from svtplay_dl.utils.stream import subtitle_filter


class postprocess:
    def __init__(self, stream, config, subfixes=None):
        self.stream = stream
        self.config = config
        self.subfixes = [x.subfix for x in subtitle_filter(subfixes)]
        self.detect = None
        for i in ["ffmpeg", "avconv"]:
            self.detect = which(i)
            if self.detect:
                break
        if self.detect is None and platform.system() == "Windows":
            path = pathlib.Path(sys.executable).parent / "ffmpeg.exe"
            if os.path.isfile(path):
                self.detect = path

    def merge(self):
        if self.detect is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = formatname(self.stream.output, self.config)
        ext = orig_filename.suffix
        new_name = orig_filename.with_suffix(f".{self.config.get('output_format')}")

        if ext == ".ts":
            audio_filename = orig_filename.with_suffix(".audio.ts")
        else:
            audio_filename = orig_filename.with_suffix(".m4a")

        cmd = [self.detect]
        if self.config.get("only_video") or not self.config.get("only_audio"):
            cmd += ["-i", str(orig_filename)]
        if self.stream.audio and self.config.get("only_audio") or not self.config.get("only_video"):
            cmd += ["-i", str(audio_filename)]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        streams = _streams(stderr)
        videotrack, audiotrack = _checktracks(streams)

        if self.config.get("merge_subtitle"):
            logging.info(f"Merge audio, video and subtitle into {new_name.name}")
        else:
            logging.info(f"Merge audio and video into {new_name.name}")

        tempfile = orig_filename.with_suffix(".temp")
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "matroska" if self.config.get("output_format") == "mkv" else "mp4"]
        if ext == ".ts":
            if audiotrack and "aac" in _getcodec(streams, audiotrack):
                arguments += ["-bsf:a", "aac_adtstoasc"]

        cmd = [self.detect]
        if self.config.get("only_video") or not self.config.get("only_audio"):
            cmd += ["-i", str(orig_filename)]
        if (self.stream.audio and self.config.get("only_audio")) or (self.stream.audio and not self.config.get("only_video")):
            cmd += ["-i", str(audio_filename)]
        if videotrack:
            arguments += ["-map", f"{videotrack}"]
        if audiotrack:
            arguments += ["-map", f"{audiotrack}"]
        if self.config.get("merge_subtitle"):
            langs = _sublanguage(self.stream, self.config, self.subfixes)
            tracks = [x for x in [videotrack, audiotrack] if x]
            subs_nr = 0
            sub_start = 0
            # find what sub track to start with. when a/v is in one file it start with 1
            # if seperate it will start with 2
            for i in tracks:
                if int(i[0]) >= sub_start:
                    sub_start += 1
            for stream_num, language in enumerate(langs, start=sub_start):
                arguments += [
                    "-map",
                    f"{str(stream_num)}:0",
                    "-c:s:" + str(subs_nr),
                    "mov_text" if self.config.get("output_format") == "mp4" else "copy",
                    "-metadata:s:s:" + str(subs_nr),
                    "language=" + language,
                ]
                subs_nr += 1
            if self.subfixes and self.config.get("get_all_subtitles"):
                for subfix in self.subfixes:
                    subfile = orig_filename.parent / (orig_filename.stem + "." + subfix + ".srt")
                    cmd += ["-i", str(subfile)]
            else:
                subfile = orig_filename.with_suffix(".srt")
                cmd += ["-i", str(subfile)]

        arguments += ["-y", str(tempfile)]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        if self.config.get("keep_original") is True:
            logging.info("Merging done, keeping original files.")
            os.rename(tempfile, orig_filename)
            return

        logging.info("Merging done, removing old files.")
        if self.config.get("only_video") or not self.config.get("only_audio"):
            os.remove(orig_filename)
        if (self.stream.audio and self.config.get("only_audio")) or (self.stream.audio and not self.config.get("only_video")):
            os.remove(audio_filename)

        if self.config.get("merge_subtitle") and not self.config.get("subtitle"):
            if self.subfixes and len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = orig_filename.parent / (orig_filename.stem + "." + subfix + ".srt")
                    os.remove(subfile)
            else:
                os.remove(subfile)
        os.rename(tempfile, new_name)


def _streams(output):
    return re.findall(r"Stream \#(\d:\d)([\[\(][^\[]+[\]\)])?([\(\)\w]+)?: (Video|Audio): (.*)", output)


def _getcodec(streams, number):
    for stream in streams:
        if stream[0] == number:
            return stream[4]
    return None


def _checktracks(streams):
    videotrack = None
    audiotrack = None
    for stream in streams:
        if stream[3] == "Video":
            videotrack = stream[0]
        if stream[3] == "Audio":
            if stream[4] == "mp3, 0 channels":
                continue
            audiotrack = stream[0]

    return videotrack, audiotrack


def _sublanguage(stream, config, subfixes):
    # parse() function partly borrowed from a guy on github. /thanks!
    # https://github.com/riobard/srt.py/blob/master/srt.py
    def parse(self):
        def parse_block(block):
            lines = block.strip("-").split("\n")
            txt = "\r\n".join(lines[2:])
            return txt

        if platform.system() == "Windows":
            fd = open(self, encoding="utf8")
        else:
            fd = open(self)
        return list(map(parse_block, fd.read().strip().replace("\r", "").split("\n\n")))

    def query(self):
        _ = parse(self)
        random_sentences = " ".join(sample(_, len(_) if len(_) < 8 else 8)).replace("\r\n", "")
        url = "https://whatlanguage.herokuapp.com"
        payload = {"query": random_sentences}
        # Note: requests handles json from version 2.4.2 and onwards so i use json.dumps for now.
        headers = {"content-type": "application/json"}
        try:
            # Note: reasonable timeout i guess? svtplay-dl is mainly used while multitasking i presume,
            # and it is heroku after all (fast enough)
            r = post(url, data=dumps(payload), headers=headers, timeout=30)
            if r.status_code == codes.ok:
                try:
                    response = r.json()
                    return response["language"]
                except TypeError:
                    return "und"
            else:
                logging.error("Server error appeared. Setting language as undetermined.")
                return "und"
        except Timeout:
            logging.error("30 seconds server timeout reached. Setting language as undetermined.")
            return "und"

    langs = []
    exceptions = {"lulesamiska": "smj", "meankieli": "fit", "jiddisch": "yid"}
    logging.info("Determining the language of the subtitle(s).")
    if config.get("get_all_subtitles"):
        for subfix in subfixes:
            if [exceptions[key] for key in exceptions.keys() if re.match(key, subfix.strip("-"))]:
                if "oversattning" in subfix.strip("-"):
                    subfix = subfix.strip("-").split(".")[0]
                else:
                    subfix = subfix.strip("-")
                langs += [exceptions[subfix]]
                continue
            sfile = formatname(stream.output, config)
            subfile = sfile.parent / (sfile.stem + "." + subfix + ".srt")
            langs += [query(subfile)]
    else:
        subfile = formatname(stream.output, config).with_suffix(".srt")
        langs += [query(subfile)]
    if len(langs) >= 2:
        logging.info("Language codes: " + ", ".join(langs))
    else:
        logging.info("Language code: " + langs[0])
    return langs
