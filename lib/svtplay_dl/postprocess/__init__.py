from json import dumps
from random import sample
import os
import platform
import re
import logging
from shutil import which
from requests import post, codes, Timeout
from re import match

from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.proc import run_program


class postprocess(object):
    def __init__(self, stream, config, subfixes=None):
        self.stream = stream
        self.config = config
        self.subfixes = subfixes
        self.detect_ffmpeg = None
        self.detect_mkvmerge = None
        self.mkv = False
        for i in ["ffmpeg", "avconv"]:
            self.detect_ffmpeg = which(i)
            if self.detect_ffmpeg:
                break
        self.detect_mkvmerge = which('mkvmerge')
        # if not self.detect_mkvmerge()

    def sublanguage(self):
        # parse() function partly borrowed from a guy on github. /thanks!
        # https://github.com/riobard/srt.py/blob/master/srt.py
        def parse(self):
            def parse_block(block):
                lines = block.strip('-').split('\n')
                txt = '\r\n'.join(lines[2:])
                return txt

            if platform.system() == "Windows":
                fd = open(self, encoding="utf8")
            else:
                fd = open(self)
            return list(map(parse_block,
                            fd.read().strip().replace('\r', '').split('\n\n')))

        def query(self):
            _ = parse(self)
            random_sentences = ' '.join(sample(_, len(_) if len(_) < 8 else 8)).replace('\r\n', '')
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
                    logging.error("Server error appeared. Setting language as undetermined.")
                    return 'und'
            except Timeout:
                logging.error("30 seconds server timeout reached. Setting language as undetermined.")
                return 'und'

        langs = []
        exceptions = {
            'lulesamiska': 'smj',
            'meankieli': 'fit',
            'jiddisch': 'yid'
        }
        if self.subfixes and len(self.subfixes) >= 2:
            logging.info("Determining the languages of the subtitles.")
        else:
            logging.info("Determining the language of the subtitle.")
        if self.config.get("get_all_subtitles"):
            for subfix in self.subfixes:
                lang = {}
                subfile = "{0}.srt".format(os.path.splitext(formatname(self.stream.output, self.config,
                                                                       self.stream.output_extention))[0] + subfix)
                # todo improve this, maybe a way to convert common filenamified
                #  words back to swedish like oversattning->översättning?
                # or rewrite the subtitle class to take the title directly from the service?
                lang['title'] = subfix.strip('-').replace('.', ' ')

                if [exceptions[key] for key in exceptions.keys() if match(key, subfix.strip('-'))]:
                    if 'oversattning' in subfix.strip('-'):
                        subfix1 = subfix.strip('-').split('.')[0]
                    else:
                        subfix1 = subfix.strip('-')
                    # langs += [exceptions[subfix]]
                    lang['lang'] = exceptions[subfix1]
                    lang['sub_file'] = subfile
                    langs.append(lang)
                    continue
                subfile = "{0}.srt".format(os.path.splitext(formatname(self.stream.output, self.config,
                                                                       self.stream.output_extention))[0] + subfix)
                lang['lang'] = query(subfile)
                lang['sub_file'] = subfile
                langs.append(lang)
        else:
            lang = {}
            subfile = "{0}.srt".format(os.path.splitext(formatname(self.stream.output, self.config,
                                                                   self.stream.output_extention))[0])
            lang['lang'] = query(subfile)
            lang['sub_file'] = subfile
            lang['title'] = None
            langs.append(lang)

        if len(langs) >= 2:
            lang_codes = set([l['lang'] for l in langs])
            logging.info("Language codes: " + ', '.join(lang_codes))
        else:
            logging.info("Language code: " + langs[0]['lang'])
        return langs

    def remux_mkv(self):
        # remux to mkv, mkvmerge prefered over ffmpeg
        # todo better error message/checking
        if self.detect_mkvmerge:
            #  TODO add something similar to this to allow config to overwrite priority
            #  and not self.config.get('prefered_mkv_tool', 'mkvmerge') == 'ffmpeg':
            self.remux_mkv_mkvmerge()
        else:
            logging.debug("Can't detect mkvmerge, using ffmpeg/avconv instead")
            self.remux_mkv_ffmpeg()  # no check needed here as the function will throw an error if ffmpeg/avconv not found

    def remux_mkv_ffmpeg(self):
        # mux to mkv with ffmpeg
        if self.detect_ffmpeg is None:
            logging.error("Cant detect ffmpeg or avconv. Can't mux files without it.")
            return
        if self.stream.finished is False:
            return

        self.mkv = True
        langs = []
        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        new_name = orig_filename
        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith('.mkv') is False:
            new_name = u"{0}.mkv".format(name)

        # First remux to mp4 if .ts file to change bitstream of audio tracks
        # this is technically only needed if we do not have a new version of ffmpeg it works with >3.0 at least.
        # TODO figure out which version and add check to only run this if needed
        if ext == '.ts':
            logging.info('Changing bitstream for TS audio by muxing to MP4')
            self.remux_mp4()
            orig_filename = u"{0}.mp4".format(name)
        cmd = [self.detect_ffmpeg, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.config.get("merge_subtitle"):
            logging.info(
                u"Muxing {0} and merging its subtitle into {1} using ffmpeg/avconv".format(orig_filename, new_name))
        else:
            logging.info(u"Muxing {0} into {1} using ffmpeg/avconv".format(orig_filename, new_name))

        tempfile = u"{0}.temp".format(orig_filename)

        arguments = ["-map", "0:{}".format(videotrack), "-map", "0:{}".format(audiotrack), "-c", "copy",
                     # "-copyts",
                     "-f", "matroska"]
        if ext == ".ts":
            arguments += ["-bsf:a", "aac_adtstoasc"]

        if self.config.get("merge_subtitle"):
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs):
                arguments += ["-map", str(stream_num + 1), "-c:s:" + str(stream_num), "copy",
                              "-metadata:s:s:" + str(stream_num), "language=" + language['lang']]
                if language['title']:
                    arguments += ["-metadata:s:s:" + str(stream_num), "title=" + language['title']]
                cmd += ['-i', language['sub_file']]

            arguments += ["-y", tempfile]
            cmd += arguments
            logging.debug('executing: %s', ' '.join(cmd))
            returncode, stdout, stderr = run_program(cmd)
            if returncode != 0:
                return

            if self.config.get("merge_subtitle") and not self.config.get("external_subtitle"):
                logging.info("Muxing done, removing subtitle files.")
                for lang in langs:
                    os.remove(lang['sub_file'])

            logging.info("Muxing done, removing the old video and audio files.")
            os.remove(orig_filename)
            os.rename(tempfile, new_name)

    def remux_mkv_mkvmerge(self):
        if self.detect_mkvmerge is None:  # this check will probably never be False  if called by remux()
            logging.error("Cant detect mkvmerge. Can't mux into matroska file without it.")
            return

        if self.stream.finished is False:
            return
        self.mkv = True

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        new_name = orig_filename
        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith('.mkv') is False:
            new_name = u"{0}.mkv".format(name)

        if ext == '.ts':
            logging.info('Changing bitstream for TS audio by muxing to MP4 first')
            self.remux_mp4()
            orig_filename = u"{0}.mp4".format(name)

        cmd = [self.detect_mkvmerge, orig_filename]
        tempfile = u"{0}.temp".format(name)

        if self.config.get("merge_subtitle"):
            langs = self.sublanguage()
            for num, lang in enumerate(langs):
                cmd.append('--language')
                cmd.append('0:' + lang['lang'])
                if lang['title']:
                    cmd.append('--track-name')
                    cmd.append('0:' + lang['title'])
                cmd.append('--sub-charset')
                cmd.append('0:UTF-8')
                cmd.append(lang['sub_file'])
        cmd.append('-o')
        cmd.append(tempfile)

        if self.config.get("merge_subtitle"):
            logging.info(u"Muxing {0} and merging its subtitle into {1} using mkvmerge".format(orig_filename, new_name))
        else:
            logging.info(u"Muxing {0} into {1} using mkvmerge".format(orig_filename, new_name))

        logging.debug('executing: %s', ' '.join(cmd))
        returncode, stdout, stderr = run_program(cmd)

        if returncode != 0:
            return

        if self.config.get("merge_subtitle") and not self.config.get("external_subtitle"):
            logging.info("Muxing done, removing subtitle files.")
            for lang in langs:
                os.remove(lang['sub_file'])

        logging.info("Muxing done, removing the old video and audio files.")

        os.remove(orig_filename)
        os.rename(tempfile, new_name)

    def remux_mp4(self):
        if self.detect_ffmpeg is None:
            logging.error("Cant detect_ffmpeg ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        new_name = orig_filename
        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith('.mp4') is False:
            new_name = u"{0}.mp4".format(name)

        cmd = [self.detect_ffmpeg, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.config.get("merge_subtitle") and not self.mkv:
            logging.info(u"Muxing {0} and merging its subtitle into {1}".format(orig_filename, new_name))
        else:
            logging.info(u"Muxing {0} into {1}".format(orig_filename, new_name))

        tempfile = u"{0}.temp".format(orig_filename)
        arguments = ["-map", "0:{}".format(videotrack), "-map", "0:{}".format(audiotrack), "-c", "copy", "-f", "mp4"]

        if ext == ".ts":
            arguments += ["-bsf:a", "aac_adtstoasc"]

        if self.config.get("merge_subtitle") and not self.mkv:
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs):
                arguments += ["-map", str(stream_num + 1), "-c:s:" + str(stream_num), "mov_text",
                              "-metadata:s:s:" + str(stream_num), "language=" + language['lang']]

                cmd += ["-i", language['sub_file']]

        arguments += ["-y", tempfile]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        if self.config.get("merge_subtitle") and not self.config.get("subtitle") and not self.mkv:
                logging.info("Muxing done, removing subtitle files.")
                for lang in langs:
                    os.remove(lang['sub_file'])
        logging.info("Muxing done, removing the old video and audio files.")
        os.remove(orig_filename)
        os.rename(tempfile, new_name)

    def merge_mp4(self):
        if self.detect_ffmpeg is None:
            logging.error("Cant detect_ffmpeg ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)

        cmd = [self.detect_ffmpeg, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.config.get("merge_subtitle") and not self.mkv:
            logging.info("Merge audio, video and subtitle into {0}".format(orig_filename))
        else:
            logging.info("Merge audio and video into {0}".format(orig_filename))

        tempfile = u"{0}.temp".format(orig_filename)
        name, ext = os.path.splitext(orig_filename)
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]

        if ext == ".ts":
            audio_filename = u"{0}.audio.ts".format(name)
            arguments += ["-bsf:a", "aac_adtstoasc"]
        else:
            audio_filename = u"{0}.m4a".format(name)

        cmd = [self.detect_ffmpeg, "-i", orig_filename, "-i", audio_filename]
        arguments += ["-map", "{}".format(videotrack), "-map", "{}".format(audiotrack)]

        if self.config.get("merge_subtitle") and not self.mkv:
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs, start=audiotrack + 1):
                arguments += ["-map", str(stream_num), "-c:s:" + str(stream_num - 2), "mov_text",
                              "-metadata:s:s:" + str(stream_num - 2), "language=" + language['lang']]

                cmd += ["-i", language['sub_file']]

        arguments += ["-y", tempfile]
        cmd += arguments
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        logging.info("Merging done, removing old files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        if self.config.get("merge_subtitle") and not self.config.get("subtitle") and not self.mkv:
            for lang in langs:
                os.remove(lang['sub_file'])
        os.rename(tempfile, orig_filename)

    def merge_mkv(self):
        # remux to mkv, mkvmerge prefered over ffmpeg
        # might add way to change this in config
        # todo better error message/checking
        if self.detect_mkvmerge:
            self.merge_mkv_mkvmerge()
        else:
            logging.info("Can't detect mkvmerge, using ffmpeg/avconv instead")
            self.merge_mkv_ffmpeg()  # no check needed here as the function will throw an error if ffmpeg/avconv not found

    def merge_mkv_mkvmerge(self):
        if self.detect_mkvmerge is None:  # this check will probably never be False unless called directly
            logging.error("Cant detect mkvmerge. Can't mux into matroska file without it.")
            return
        if self.stream.finished is False:
            return

        self.mkv = True

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        new_name = orig_filename

        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith('.mkv') is False:
            new_name = u"{0}.mkv".format(name)

        tempfile = u"{0}.temp".format(orig_filename)
        # new_name = u"{0}.mkv".format(name)

        if ext == '.ts':
            logging.info('Chaning bitstream for TS audio with ffmpeg/avconv')
            self._clean_ts_audio()
            audio_filename = u"{0}.audio.mp4".format(name)
        else:
            audio_filename = u"{0}.m4a".format(name)

        cmd = [self.detect_mkvmerge, orig_filename, audio_filename]

        if self.config.get("merge_subtitle"):
            langs = self.sublanguage()
            for num, lang in enumerate(langs):
                cmd.append('--language')
                cmd.append('0:' + lang['lang'])
                if lang['title']:
                    cmd.append('--track-name')
                    cmd.append('0:' + lang['title'])
                cmd.append('--sub-charset')
                cmd.append('0:UTF-8')
                cmd.append(lang['sub_file'])
        cmd.append('-o')
        cmd.append(tempfile)

        if self.config.get("merge_subtitle"):
            logging.info(u"Muxing {0} and merging its subtitle into {1} using mkvmerge".format(orig_filename, new_name))
        else:
            logging.info(u"Muxing {0} into {1} using mkvmerge".format(orig_filename, new_name))

        logging.debug('executing: %s', ' '.join(cmd))
        returncode, stdout, stderr = run_program(cmd)

        if returncode != 0:
            return

        if self.config.get("merge_subtitle") and not self.config.get("external_subtitle"):
            logging.info("Muxing done, removing subtitle files.")
            for lang in langs:
                os.remove(lang['sub_file'])
        logging.info("Muxing done, removing the old video and audio files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        os.rename(tempfile, new_name)

    def merge_mkv_ffmpeg(self):
        if self.detect_ffmpeg is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return
        if self.stream.finished is False:
            return

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        new_filename = orig_filename
        if formatname(self.stream.output, self.config, self.stream.output_extention).endswith('.mkv') is False:
            new_filename = u"{0}.mkv".format(name)

        cmd = [self.detect_ffmpeg, "-i", orig_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        if self.config.get("merge_subtitle"):
            logging.info("Merge audio, video and subtitle into {0}".format(new_filename))
        else:
            logging.info("Merge audio and video into {0}".format(new_filename))

        tempfile = u"{0}.temp".format(orig_filename)

        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4"]

        if ext == ".ts":
            audio_filename = u"{0}.audio.ts".format(name)
            arguments += ["-bsf:a", "aac_adtstoasc"]
        else:
            audio_filename = u"{0}.m4a".format(name)

        cmd = [self.detect_ffmpeg, "-i", orig_filename, "-i", audio_filename]
        arguments += ["-map", "{}".format(videotrack), "-map", "{}".format(audiotrack)]

        if self.config.get("merge_subtitle") and not self.mkv:
            langs = self.sublanguage()
            for stream_num, language in enumerate(langs, start=audiotrack + 1):
                arguments += ["-map", str(stream_num), "-c:s:" + str(stream_num - 2), "copy",
                              "-metadata:s:s:" + str(stream_num - 2), "language=" + language['lang']]
                if language['title']:
                    arguments += ["-metadata:s:s:" + str(stream_num), "title=" + language['title']]
                cmd += ['-i', language['sub_file']]

        arguments += ["-y", tempfile]
        cmd += arguments
        logging.debug('executing: %s', ' '.join(cmd))
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        logging.info("Merging done, removing old files.")
        os.remove(orig_filename)
        os.remove(audio_filename)
        if self.config.get("merge_subtitle") and not self.config.get("external_subtitle") and not self.mkv:
            for lang in langs:
                os.remove(lang['sub_file'])
        os.rename(tempfile, new_filename)

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

    def _clean_ts_audio(self):
        if self.detect_ffmpeg is None:
            logging.error("Cant detect ffmpeg or avconv. Cant mux files without it.")
            return

        orig_filename = formatname(self.stream.output, self.config, self.stream.output_extention)
        name, ext = os.path.splitext(orig_filename)
        tempfile = u"{0}.temp".format(name)
        arguments = ["-c:a", "copy", "-f", "mp4", "-bsf:a", "aac_adtstoasc"]
        audio_filename = u"{0}.audio.mp4".format(name)
        cmd = [self.detect_ffmpeg, "-i", audio_filename]
        _, stdout, stderr = run_program(cmd, False)  # return 1 is good here.
        videotrack, audiotrack = self._checktracks(stderr)

        logging.info('Fixing bitstream for %s', audio_filename)
        cmd = [self.detect_ffmpeg, "-i", audio_filename]

        arguments += ["-y", tempfile]
        cmd += arguments
        logging.debug('executing: %s', ' '.join(cmd))
        returncode, stdout, stderr = run_program(cmd)
        if returncode != 0:
            return

        logging.info("Audio cleaning done, removing old files.")
        os.remove(audio_filename)
        os.rename(tempfile, audio_filename)
