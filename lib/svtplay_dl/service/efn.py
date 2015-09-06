from __future__ import absolute_import
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.error import ServiceError


class Efn(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.efn.se"]

    def get(self, options):
        data = self.get_urldata()

        match = re.search('data-hls="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find video info")
            return

        streams = hlsparse(match.group(1), self.http.request("get", match.group(1)).text)
        if streams:
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)