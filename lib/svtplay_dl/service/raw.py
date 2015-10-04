from __future__ import absolute_import
import copy
import os

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.log import log


class Raw(Service):
    def get(self, options):
        data = self.get_urldata()

        if self.exclude(options):
            return

        extention = False
        filename = os.path.basename(self.url[:self.url.rfind("/")-1])
        if options.output and os.path.isdir(options.output):
            options.output = os.path.join(os.path.dirname(options.output), filename)
            extention = True
        elif options.output is None:
            options.output = "%s" % filename
            extention = True

        if self.url.find(".f4m") > 0:
            if extention:
                options.output = "%s.flv" % options.output

            streams = hdsparse(options, self.http.request("get", self.url, params={"hdcore": "3.7.0"}), self.url)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        if self.url.find(".m3u8") > 0:
            streams = hlsparse(options, self.http.request("get", self.url), self.url)
            if extention:
                options.output = "%s.ts" % options.output

            for n in list(streams.keys()):
                yield streams[n]
