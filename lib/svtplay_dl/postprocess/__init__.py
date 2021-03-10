import logging
import os
import platform
import re
from json import dumps
from random import sample
from re import match
from shutil import which

from requests import codes
from requests import post
from requests import Timeout
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.proc import run_program


class postprocess:
    def __init__(self, stream, config, subfixes=None):
        self.stream = stream
        self.config = config
        self.subfixes = subfixes
        self.detect = None
        for i in ["ffmpeg", "avconv"]:
            self.detect = which(i)
            if self.detect:
                break

    def remux(self):
        if self.detect is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith(".mp4") is False:
            orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
            name, ext = os.path.splitext(orig_filename)
            new_name = f"{name}.mp4"

            cmd = [self.detect, "-i", orig_filename]
            _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
            streams = _streams(stderr)
            videotrack, audiotrack = _checktracks(streams)

            if self.config.get("merge_subtitle"):
                logging.info(f"Muxing {orig_filename} and merging its subtitle into {new_name}")
            else:
                logging.info(f"Muxing {orig_filename} into {new_name}")

            tempfile = f"{orig_filename}.temp"
            arguments = []
            if videotrack:
                arguments += ["-map", f"{videotrack}"]
            if audiotrack:
                arguments += ["-map", f"{audiotrack}"]
            arguments += ["-c", "copy", "-f", "mp4"]
            if ext == ".ts" and streams and "aac" in _getcodec(streams, audiotrack):
                arguments += ["-bsf:a", "aac_adtstoasc"]

            if self.config.get("merge_subtitle"):
                langs = _sublanguage(self.stream, self.config, self.subfixes)
                for stream_num, language in enumerate(langs):
                    arguments += [
                        "-map",
                        str(stream_num + 1),
                        "-c:s:" + str(stream_num),
                        "mov_text",
                        "-metadata:s:s:" + str(stream_num),
                        "language=" + language,
                    ]
                if self.subfixes and len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{}.srt".format(name + subfix)
                        cmd += ["-i", subfile]
                else:
                    subfile = f"{name}.srt"
                    cmd += ["-i", subfile]

            arguments += ["-y", tempfile]
            cmd += arguments
            returncode, stdout, stderr = run_program(cmd)
            if returncode != 0:
                return

            if self.config.get("merge_subtitle") and not self.config.get("subtitle"):
                logging.info("Muxing done, removing the old files.")
                if self.subfixes and len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{}.srt".format(name + subfix)
                        os.remove(subfile)
                else:
                    os.remove(subfile)
            else:
                logging.info("Muxing done, removing the old file.")
            os.remove(orig_filename)
            os.rename(tempfile, new_name)

    def merge(self):
        if self.detect is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        if ext == ".ts":
            audio_filename = f"{name}.audio.ts"
        else:
            audio_filename = f"{name}.m4a"

        cmd = [self.detect]
        if self.config.get("only_video") or not self.config.get("only_audio"):
            cmd += ["-i", orig_filename]
        if self.config.get("only_audio") or not self.config.get("only_video"):
            cmd += ["-i", audio_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        streams = _streams(stderr)
        videotrack, audiotrack = _checktracks(streams)

        if self.config.get("merge_subtitle"):
            logging.info(f"Merge audio, video and subtitle into {orig_filename}")
        else:
            logging.info(f"Merge audio and video into {orig_filename}")

        tempfile = f"{orig_filename}.temp"
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]
        if ext == ".ts":
            if audiotrack and "aac" in _getcodec(streams, audiotrack):
                arguments += ["-bsf:a", "aac_adtstoasc"]
        cmd = [self.detect]
        if self.config.get("only_video") or not self.config.get("only_audio"):
            cmd += ["-i", orig_filename]
        if self.config.get("only_audio") or not self.config.get("only_video"):
            cmd += ["-i", audio_filename]
        if videotrack:
            arguments += ["-map", f"{videotrack}"]
        if audiotrack:
            arguments += ["-map", f"{audiotrack}"]
        if self.config.get("merge_subtitle"):
            langs = _sublanguage(self.stream, self.config, self.subfixes)
            tracks = [x for x in [videotrack, audiotrack] if x]
            for stream_num, language in enumerate(langs, start=len(tracks)):
                arguments += [
                    "-map",
                    str(stream_num),
                    "-c:s:" + str(stream_num - 2),
                    "mov_text",
                    "-metadata:s:s:" + str(stream_num - 2),
                    "language=" + language,
                ]
            if self.subfixes and len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{}.srt".format(name + subfix)
                    cmd += ["-i", subfile]
            else:
                subfile = f"{name}.srt"
                cmd += ["-i", subfile]

        arguments += ["-y", tempfile]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        logging.info("Merging done, removing old files.")
        if self.config.get("only_video") or not self.config.get("only_audio"):
            os.remove(orig_filename)
        if self.config.get("only_audio") or not self.config.get("only_video"):
            os.remove(audio_filename)

        if self.config.get("merge_subtitle") and not self.config.get("subtitle"):
            if self.subfixes and len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{}.srt".format(name + subfix)
                    os.remove(subfile)
            else:
                os.remove(subfile)
        os.rename(tempfile, orig_filename)


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
    if subfixes and len(subfixes) >= 2:
        logging.info("Determining the languages of the subtitles.")
    else:
        logging.info("Determining the language of the subtitle.")
    if config.get("get_all_subtitles"):
        for subfix in subfixes:
            if [exceptions[key] for key in exceptions.keys() if match(key, subfix.strip("-"))]:
                if "oversattning" in subfix.strip("-"):
                    subfix = subfix.strip("-").split(".")[0]
                else:
                    subfix = subfix.strip("-")
                langs += [exceptions[subfix]]
                continue
            subfile = "{}.srt".format(os.path.splitext(formatname(stream.output, config, stream.output_extention))[0] + subfix)
            langs += [query(subfile)]
    else:
        subfile = "{}.srt".format(os.path.splitext(formatname(stream.output, config, stream.output_extention))[0])
        langs += [query(subfile)]
    if len(langs) >= 2:
        logging.info("Language codes: " + ", ".join(langs))
    else:
        logging.info("Language code: " + langs[0])
    return langs
