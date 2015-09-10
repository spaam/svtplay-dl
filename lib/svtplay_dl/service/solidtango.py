# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.error import ServiceError

class Solidtango(Service):
    supported_domains = ['skkplay.se', 'skkplay.solidtango.com']

    def get(self, options):
        data = self.get_urldata()

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        match = re.search(r'<title>(http[^<]+)</title>', data)
        if match:
            data = self.http.request("get", match.group(1)).text

        match = re.search('html5_source: "([^"]+)"', data)
        if match:
            streams = hlsparse(match.group(1), self.http.request("get", match.group(1)).text)
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
        else:
            yield ServiceError("Can't find video info. if there is a video on the page. its a bug.")
            return