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

    def sublanguage(self):
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
        if self.subfixes and len(self.subfixes) >= 2:
            logging.info("Determining the languages of the subtitles.")
        else:
            logging.info("Determining the language of the subtitle.")
        if self.config.get("get_all_subtitles"):
            for subfix in self.subfixes:
                if [exceptions[key] for key in exceptions.keys() if match(key, subfix.strip("-"))]:
                    if "oversattning" in subfix.strip("-"):
                        subfix = subfix.strip("-").split(".")[0]
                    else:
                        subfix = subfix.strip("-")
                    langs += [exceptions[subfix]]
                    continue
                subfile = "{}.srt".format(os.path.splitext(formatname(self.stream.output, self.config, self.stream.output_extention))[0] + subfix)
                langs += [query(subfile)]
        else:
            subfile = "{}.srt".format(os.path.splitext(formatname(self.stream.output, self.config, self.stream.output_extention))[0])
            langs += [query(subfile)]
        if len(langs) >= 2:
            logging.info("Language codes: " + ", ".join(langs))
        else:
            logging.info("Language code: " + langs[0])
        return langs

    def remux(self):
        if self.detect is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith(".mp4") is False:
            orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
            name, ext = os.path.splitext(orig_filename)
            new_name = "{}.mp4".format(name)

            cmd = [self.detect, "-i", orig_filename]
            _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
            videotrack, audiotrack = self._checktracks(stderr)

            if self.config.get("merge_subtitle"):
                logging.info("Muxing {} and merging its subtitle into {}".format(orig_filename, new_name))
            else:
                logging.info("Muxing {} into {}".format(orig_filename, new_name))

            tempfile = "{}.temp".format(orig_filename)
            arguments = ["-map", "0:{}".format(videotrack), "-map", "0:{}".format(audiotrack), "-c", "copy", "-f", "mp4"]
            if ext == ".ts":
                arguments += ["-bsf:a", "aac_adtstoasc"]

            if self.config.get("merge_subtitle"):
                langs = self.sublanguage()
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
                    subfile = "{}.srt".format(name)
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

        cmd = [self.detect, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.config.get("merge_subtitle"):
            logging.info("Merge audio, video and subtitle into {}".format(orig_filename))
        else:
            logging.info("Merge audio and video into {}".format(orig_filename))

        tempfile = "{}.temp".format(orig_filename)
        name, ext = os.path.splitext(orig_filename)
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]
        if ext == ".ts":
            audio_filename = "{}.audio.ts".format(name)
            arguments += ["-bsf:a", "aac_adtstoasc"]
        else:
            audio_filename = "{}.m4a".format(name)
        cmd = [self.detect, "-i", orig_filename, "-i", audio_filename]

        arguments += ["-map", "{}".format(videotrack), "-map", "{}".format(audiotrack)]
        if self.config.get("merge_subtitle"):
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs, start=audiotrack + 1):
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
                subfile = "{}.srt".format(name)
                cmd += ["-i", subfile]

        arguments += ["-y", tempfile]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        logging.info("Merging done, removing old files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        if self.config.get("merge_subtitle") and not self.config.get("subtitle"):
            if self.subfixes and len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{}.srt".format(name + subfix)
                    os.remove(subfile)
            else:
                os.remove(subfile)
        os.rename(tempfile, orig_filename)

    def _checktracks(self, output):
        allstuff = re.findall(r"Stream \#\d:(\d)\[[^\[]+\]([\(\)\w]+)?: (Video|Audio): (.*)", output)
        videotrack = 0
        audiotrack = 1
        for stream in allstuff:
            if stream[2] == "Video":
                videotrack = stream[0]
            if stream[2] == "Audio":
                if stream[3] == "mp3, 0 channels":
                    continue
                audiotrack = stream[0]

        return videotrack, audiotrack
