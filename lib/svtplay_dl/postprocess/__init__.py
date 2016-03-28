import subprocess
import os


from svtplay_dl.log import log
from svtplay_dl.utils import which


class postprocess(object):
    def __init__(self, stream):
        self.stream = stream
        self.detect = False
        for i in ["ffmpeg", "avconv"]:
            self.detect = which(i)
            if self.detect:
                break

    def remux(self):
        if self.detect is False:
            log.error("Cant detect ffmpeg or avconv. cant mux files without it")
            return
        if self.stream.finished is False:
            return
        orig_filename = self.stream.options.output
        new_name = "{0}.mp4".format(os.path.splitext(self.stream.options.output)[0])

        log.info("Muxing {0} into {1}".format(orig_filename, new_name))
        tempfile = "{0}.temp".format(self.stream.options.output)
        name, ext = os.path.splitext(orig_filename)
        arguments = ["-c", "copy", "-copyts", "-f", "mp4"]
        if ext == "ts":
            arguments += ["-bsf:a", "aac_adtstoasc"]
        arguments += ["-y", tempfile]
        cmd = [self.detect, "-i", orig_filename]
        cmd += arguments
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            stderr = stderr.decode('utf-8', 'replace')
            msg = stderr.strip().split('\n')[-1]
            log.error("Something went wrong: {0}".format(msg))
            return
        log.info("Muxing done. removing the old file.")
        os.remove(self.stream.options.output)
        os.rename(tempfile, new_name)

    def merge(self):
        if self.detect is False:
            log.error("Cant detect ffmpeg or avconv. cant mux files without it")
            return

        if self.stream.finished is False:
            return
        orig_filename = self.stream.options.output
        log.info("Merge audio and video into {0}".format(orig_filename))
        tempfile = "{0}.temp".format(self.stream.options.output)
        audio_filename = "{0}.m4a".format(os.path.splitext(self.stream.options.output)[0])
        arguments = ["-c:v", "copy", "-c:a", "copy", "-f", "mp4", "-y", tempfile]
        cmd = [self.detect, "-i", orig_filename, "-i", audio_filename]
        cmd += arguments
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            stderr = stderr.decode('utf-8', 'replace')
            msg = stderr.strip().split('\n')[-1]
            log.error("Something went wrong: {0}".format(msg))
            return
        log.info("Merging done, removing old files.")
        os.remove(self.stream.options.output)
        os.remove(audio_filename)
        os.rename(tempfile, self.stream.options.output)