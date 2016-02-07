from __future__ import absolute_import
import re

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Efn(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.efn.se"]

    def get(self):
        match = re.search('data-hls="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find video info")
            return

        streams = hlsparse(self.options, self.http.request("get", match.group(1)), match.group(1))
        if streams:
            for n in list(streams.keys()):
                yield streams[n]