# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import subprocess
import re
import shlex
import os

from svtplay_dl.log import log
from svtplay_dl.utils import is_py2
from svtplay_dl.fetcher import VideoRetriever

class RTMP(VideoRetriever):
    def name(self):
        return "hds"

    def download(self):
        """ Get the stream from RTMP """
        args = []
        if self.options.live:
            args.append("-v")

        if self.options.resume:
            args.append("-e")

        extension = re.search(r"(\.[a-z0-9]+)$", self.url)
        if self.options.output != "-":
            if not extension:
                self.options.output = "%s.flv" % self.options.output
            else:
                self.options.output = self.options.output + extension.group(1)
            log.info("Outfile: %s", self.options.output)
            if os.path.isfile(self.options.output) and not self.options.force:
                log.info("File already exists. use --force to overwrite")
                return
            args += ["-o", self.options.output]
        if self.options.silent or self.options.output == "-":
            args.append("-q")
        if self.options.other:
            if is_py2:
                args += shlex.split(self.options.other.encode("utf-8"))
            else:
                args += shlex.split(self.options.other)

        if self.options.verbose:
            args.append("-V")

        command = ["rtmpdump", "-r", self.url] + args
        log.debug("Running: %s", " ".join(command))
        try:
            subprocess.call(command)
        except OSError as e:
            log.error("Could not execute rtmpdump: " + e.strerror)

