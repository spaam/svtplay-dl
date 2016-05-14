from __future__ import absolute_import
import os

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse


class Raw(Service):
    def get(self):
        data = self.get_urldata()

        if self.exclude():
            return

        extention = False
        filename = os.path.basename(self.url[:self.url.rfind("/")-1])
        if self.options.output and os.path.isdir(self.options.output):
            self.options.output = os.path.join(os.path.dirname(self.options.output), filename)
            extention = True
        elif self.options.output is None:
            self.options.output = "%s" % filename
            extention = True

        if self.url.find(".f4m") > 0:
            if extention:
                self.options.output = "%s.flv" % self.options.output

            streams = hdsparse(self.options, self.http.request("get", self.url, params={"hdcore": "3.7.0"}), self.url)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        if self.url.find(".m3u8") > 0:
            streams = hlsparse(self.options, self.http.request("get", self.url), self.url)
            if extention:
                self.options.output = "%s.ts" % self.options.output

            for n in list(streams.keys()):
                yield streams[n]
