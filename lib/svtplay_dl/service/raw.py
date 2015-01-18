from __future__ import absolute_import
import copy
import os

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse, HLS
from svtplay_dl.log import log

class Raw(Service):
    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return

        if self.exclude(options):
            return

        if self.url.find(".f4m") > 0:
            if options.output is None:
                filename = os.path.basename(self.url[:self.url.rfind("/")-1])
                options.output = "%s.flv" % filename
            streams = hdsparse(copy.copy(options), self.url)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        if self.url.find(".m3u8") > 0:
            streams = hlsparse(self.url)
            if options.output is None:
                filename = os.path.basename(self.url[:self.url.rfind("/")-1])
                options.output = "%s.ts" % filename
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
