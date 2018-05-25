# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import subprocess
import shlex

from svtplay_dl.log import log
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.utils.output import output, formatname


class RTMP(VideoRetriever):
    @property
    def name(self):
        return "rtmp"

    def download(self):
        """ Get the stream from RTMP """
        self.output_extention = "flv"
        args = []
        if self.config.get("live"):
            args.append("-v")

        if self.config.get("resume"):
            args.append("-e")

        file_d = output(self.output, self.config, "flv", False)
        if file_d is None:
            return
        args += ["-o", formatname(self.output, self.config, "flv")]
        if self.config.get("silent"):
            args.append("-q")
        if self.kwargs.get("other"):
            args += shlex.split(self.kwargs.pop("other"))

        if self.config.get("verbose"):
            args.append("-V")

        command = ["rtmpdump", "-r", self.url] + args
        log.debug("Running: {0}".format(" ".join(command)))
        try:
            subprocess.call(command)
        except OSError as e:
            log.error("Could not execute rtmpdump: {0}".format(e.strerror))
            return
        self.finished = True
