from requests import post, codes, Timeout
from json import dumps
from random import sample
import subprocess
import os

from svtplay_dl.log import log
from svtplay_dl.utils import which


class postprocess(object):
    def __init__(self, stream, options, subfixes = []):
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
                lines   = block.strip('-').split('\n')
                txt     = '\r\n'.join(lines[2:])
                return txt
            return list(map(parse_block,
                        open(self).read().strip().replace('\r', '').split('\n\n')))
        
        def query(self):
            random_sentences = ' '.join(sample(parse(self),8)).replace('\r\n', '')
            url = 'https://whatlanguage.herokuapp.com'
            payload = { "query": random_sentences }
            headers = {'content-type': 'application/json'} # Note: requests handles json from version 2.4.2 and onwards so i use json.dumps for now.
            try:
                r = post(url, data=dumps(payload), headers=headers, timeout=30) # Note: reasonable timeout i guess? svtplay-dl is mainly used while multitasking i presume, and it is heroku after all (fast enough)
                if r.status_code == codes.ok:
                    response = r.json()
                    return response['language']
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
        else: log.info("Determining the language of the subtitle.")
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
                subfile = "{}.srt".format(os.path.splitext(self.stream.options.output)[0] + subfix)
                langs += [query(subfile)]
        else:
            subfile = "{}.srt".format(os.path.splitext(self.stream.options.output)[0])
            langs += [query(subfile)]
        if len(langs) >= 2:
            log.info("Language codes: " + ', '.join(langs))
        else: log.info("Language code: " + langs[0])
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
            new_name = "{}.mp4".format(name)

            if self.merge_subtitle:
                log.info("Muxing %s and merging its subtitle into %s", orig_filename, new_name)
            else:
                log.info("Muxing %s into %s", orig_filename, new_name)
            
            tempfile = "{}.temp".format(orig_filename)
            arguments = ["-map", "0:v", "-map", "0:a", "-c", "copy", "-copyts", "-f", "mp4"]
            if ext == ".ts":
                arguments += ["-bsf:a", "aac_adtstoasc"]
            cmd = [self.detect, "-i", orig_filename]
            
            if self.merge_subtitle:
                langs = self.sublanguage()
                for stream_num, language in enumerate(langs):
                    arguments += ["-map", str(stream_num + 1), "-c:s:" + str(stream_num), "mov_text", "-metadata:s:s:" + str(stream_num), "language=" + language]
                if len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{}.srt".format(name + subfix)
                        cmd += ["-i", subfile]
                else:
                    subfile = "{}.srt".format(name)
                    cmd += ["-i", subfile]
                
            arguments += ["-y", tempfile]
            cmd += arguments
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                stderr = stderr.decode('utf-8', 'replace')
                msg = stderr.strip().split('\n')[-1]
                log.error("Something went wrong: %s", msg)
                return
            
            if self.merge_subtitle and not self.external_subtitle:
                log.info("Muxing done, removing the old files.")
                if len(self.subfixes) >= 2:
                    for subfix in self.subfixes:
                        subfile = "{}.srt".format(name + subfix)
                        os.remove(subfile)
                else: os.remove(subfile)
            else: log.info("Muxing done, removing the old file.")
            os.remove(orig_filename)
            os.rename(tempfile, new_name)

    def merge(self):
        if self.detect is None:
            log.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = self.stream.options.output
        if self.merge_subtitle:
            log.info("Merge audio, video and subtitle into %s", orig_filename)
        else:
            log.info("Merge audio and video into %s", orig_filename)
        
        tempfile = "{}.temp".format(orig_filename)
        name = os.path.splitext(orig_filename)[0]
        audio_filename = "{}.m4a".format(name)
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]
        cmd = [self.detect, "-i", orig_filename, "-i", audio_filename]

        if self.merge_subtitle:
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs, start = 2):
                arguments += ["-map", "0", "-map", "1", "-map", str(stream_num), "-c:s:" + str(stream_num - 2), "mov_text", "-metadata:s:s:" + str(stream_num - 2), "language=" + language]
            if len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{}.srt".format(name + subfix)
                    cmd += ["-i", subfile]
            else:
                subfile = "{}.srt".format(name)
                cmd += ["-i", subfile]
            
        arguments += ["-y", tempfile]
        cmd += arguments
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            stderr = stderr.decode('utf-8', 'replace')
            msg = stderr.strip().split('\n')[-1]
            log.error("Something went wrong: %s", msg)
            return

        log.info("Merging done, removing old files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        if self.merge_subtitle and not self.external_subtitle:
            if len(self.subfixes) >= 2:
                for subfix in self.subfixes:
                    subfile = "{}.srt".format(name + subfix)
                    os.remove(subfile)
            else: os.remove(subfile)
        os.rename(tempfile, orig_filename)
