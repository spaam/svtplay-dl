from __future__ import absolute_import
import os
import re

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.dash import dashparse


class Raw(Service):
    def get(self):
        if self.exclude():
            return

        extention = False
        filename = os.path.basename(self.url[:self.url.rfind("/")])
        if self.options.output and os.path.isdir(self.options.output):
            self.options.output = os.path.join(os.path.dirname(self.options.output), filename)
            extention = True
        elif self.options.output is None:
            self.options.output = filename
            extention = True

        streams = []
        if re.search(".f4m", self.url):
            if extention:
                self.options.output = "{0}.flv".format(self.options.output)

            streams.append(hdsparse(self.options, self.http.request("get", self.url, params={"hdcore": "3.7.0"}), self.url))

        if re.search(".m3u8", self.url):
            streams.append(hlsparse(self.options, self.http.request("get", self.url), self.url))

        if re.search(".mpd", self.url):
            streams.append(dashparse(self.options, self.http.request("get", self.url), self.url))

        for stream in streams:
            if stream:
                for n in list(stream.keys()):
                    yield stream[n]
