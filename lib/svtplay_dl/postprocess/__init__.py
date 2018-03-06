from json import dumps
from random import sample
import os
import platform
import re
from requests import post, codes, Timeout

from svtplay_dl.log import log
from svtplay_dl.utils import which, is_py3, run_program


class postprocess(object):
    def __init__(self, stream, options, subfixes=[]):
        self.stream = stream
        self.merge_subtitle = options.merge_subtitle
        self.external_subtitle = options.subtitle
        self.get_all_subtitles = options.get_all_subtitles
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
                lines = block.strip('-').split('\n')
                txt = '\r\n'.join(lines[2:])
                return txt

            if platform.system() == "Windows" and is_py3:
                fd = open(self, encoding="utf8")
            else:
                fd = open(self)
            return list(map(parse_block,
                            fd.read().strip().replace('\r', '').split('\n\n')))

        def query(self):
            random_sentences = ' '.join(sample(parse(self), 8)).replace('\r\n', '')
            url = 'https://whatlanguage.herokuapp.com'
            payload = {"query": random_sentences}
            # Note: requests handles json from version 2.4.2 and onwards so i use json.dumps for now.
            headers = {'content-type': 'application/json'}
            try:
                # Note: reasonable timeout i guess? svtplay-dl is mainly used while multitasking i presume,
                # and it is heroku after all (fast enough)
                r = post(url, data=dumps(payload), headers=headers, timeout=30)
                if r.status_code == codes.ok:
                    try:
                        response = r.json()
                        return response['language']
                    except TypeError:
                        return 'und'
                else:
                    log.error("Server error appeared. Setting language as undetermined.")
                    return 'und'
            except Timeout:
                log.error("30 seconds server timeout reached. Setting language as undetermined.")
                return 'und'

        langs = []
        exceptions = {
            'lulesamiska': 'smj',
            'meankieli': 'fit',
            'jiddisch': 'yid'
        }
        if len(self.subfixes) >= 2:
            log.info("Determining the languages of the subtitles.")
        else:
            log.info("Determining the language of the subtitle.")
        if self.get_all_subtitles:
            from re import match
            for subfix in self.subfixes:
                if [exceptions[key] for key in exceptions.keys() if match(key, subfix.strip('-'))]:
                    if 'oversattning' in subfix.strip('-'):
                        subfix = subfix.strip('-').split('.')[0]
                    else:
                        subfix = subfix.strip('-')
                    langs += [exceptions[subfix]]
                    continue
                subfile = "{0}.srt".format(os.path.splitext(self.stream.options.output)[0] + subfix)
                langs += [query(subfile)]
        else:
            subfile = "{0}.srt".format(os.path.splitext(self.stream.options.output)[0])
            langs += [query(subfile)]
        if len(langs) >= 2:
            log.info("Language codes: " + ', '.join(langs))
        else:
            log.info("Language code: " + langs[0])
        return langs

    def remux(self):
        if self.detect is None:
            log.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        if self.stream.options.output.endswith('.mp4') is False:
            orig_filename = self.stream.options.output
            name, ext = os.path.splitext(orig_filename)
            new_name = u"{0}.mp4".format(name)

            cmd = [self.detect, "-i", orig_filename]
            _, stdout, stderr = run_program(cmd, False) # return 1 is good here.
            videotrack, audiotrack = self._checktracks(stderr)

            if self.merge_subtitle:
                log.info(u"Muxing {0} and merging its subtitle into {1}".format(orig_filename, new_name))
            else:
                log.info(u"Muxing {0} into {1}".format(orig_filename, new_name))

            tempfile = u"{0}.temp".format(orig_filename)
            arguments = ["-map", "0:{}".format(videotrack), "-map", "0:{}".format(audiotrack), "-c", "copy", "-copyts", "-f", "mp4"]
            if ext == ".ts":
                arguments += ["-bsf:a", "aac_adtstoasc"]

            if self.merge_subtitle:
                langs = self.sublanguage()
                for stream_num, language in enumerate(langs):
                    arguments += ["-map", str(stream_num + 1), "-c:s:" + str(stream_num), "mov_text",
                                  "-metadata:s:s:" + str(stream_num), "language=" + language]
                if len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{0}.srt".format(name + subfix)
                        cmd += ["-i", subfile]
                else:
                    subfile = "{0}.srt".format(name)
                    cmd += ["-i", subfile]

            arguments += ["-y", tempfile]
            cmd += arguments
            returncode, stdout, stderr = run_program(cmd)
            if returncode != 0:
                return

            if self.merge_subtitle and not self.external_subtitle:
                log.info("Muxing done, removing the old files.")
                if len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{0}.srt".format(name + subfix)
                        os.remove(subfile)
                else:
                    os.remove(subfile)
            else:
                log.info("Muxing done, removing the old file.")
            os.remove(orig_filename)
            os.rename(tempfile, new_name)

    def merge(self):
        if self.detect is None:
            log.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = self.stream.options.output

        cmd = [self.detect, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.merge_subtitle:
            log.info("Merge audio, video and subtitle into {0}".format(orig_filename))
        else:
            log.info("Merge audio and video into {0}".format(orig_filename))

        tempfile = u"{0}.temp".format(orig_filename)
        name, ext = os.path.splitext(orig_filename)
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]
        if ext == ".ts":
            audio_filename = u"{0}.audio.ts".format(name)
            arguments += ["-bsf:a", "aac_adtstoasc"]
        else:
            audio_filename = u"{0}.m4a".format(name)
        cmd = [self.detect, "-i", orig_filename, "-i", audio_filename]

        if self.merge_subtitle:
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs, start=audiotrack + 1):
                arguments += ["-map", "{}".format(videotrack), "-map", "{}".format(audiotrack), "-map", str(stream_num), "-c:s:" + str(stream_num - 2), "mov_text",
                              "-metadata:s:s:" + str(stream_num - 2), "language=" + language]
            if len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{0}.srt".format(name + subfix)
                    cmd += ["-i", subfile]
            else:
                subfile = "{0}.srt".format(name)
                cmd += ["-i", subfile]

        arguments += ["-y", tempfile]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 1:
            return

        log.info("Merging done, removing old files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        if self.merge_subtitle and not self.external_subtitle:
            if len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{0}.srt".format(name + subfix)
                    os.remove(subfile)
            else:
                os.remove(subfile)
        os.rename(tempfile, orig_filename)

    def _checktracks(self, output):
        allstuff = re.findall("Stream \#\d:(\d)\[[^\[]+\]: (Video|Audio): (.*)", output)
        videotrack = 0
        audiotrack = 1
        for stream in allstuff:
            if stream[1] == "Video":
                videotrack = stream[0]
            if stream[1] == "Audio":
                if stream[2] == "mp3, 0 channels":
                    continue
                audiotrack = stream[0]

        return videotrack, audiotrack
