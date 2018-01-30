# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import subprocess
import shlex

from svtplay_dl.log import log
from svtplay_dl.utils import is_py2
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.output import output


class RTMP(VideoRetriever):
    def name(self):
        return "rtmp"

    def download(self):
        """ Get the stream from RTMP """
        args = []
        if self.options.live:
            args.append("-v")

        if self.options.resume:
            args.append("-e")

        file_d = output(self.options, "flv", False)
        if file_d is None:
            return
        args += ["-o", self.options.output]
        if self.options.silent:
            args.append("-q")
        if self.options.other:
            if is_py2:
                args += shlex.split(self.options.other.encode("utf-8"))
            else:
                args += shlex.split(self.options.other)

        if self.options.verbose:
            args.append("-V")

        command = ["rtmpdump", "-r", self.url] + args
        log.debug("Running: {0}".format(" ".join(command)))
        try:
            subprocess.call(command)
        except OSError as e:
            log.error("Could not execute rtmpdump: {0}".format(e.strerror))
            return
        self.finished = True
