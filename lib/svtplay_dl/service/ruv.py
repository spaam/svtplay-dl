# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import json

from svtplay_dl.service import Service
from svtplay_dl.log import log
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.hls import HLS, hlsparse

class Ruv(Service):
    supported_domains = ['ruv.is']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return

        if self.exclude(options):
            return

        match = re.search(r'"([^"]+geo.php)"', data)
        if match:
            error, data = get_http_data(match.group(1))
            if error:
                log.error("Cant get stream info")
                return
            match = re.search(r'punktur=\(([^ ]+)\)', data)
            if match:
                janson = json.loads(match.group(1))
                options.live = checklive(janson["result"][1])
                streams = hlsparse(janson["result"][1])
                for n in list(streams.keys()):
                    yield HLS(copy.copy(options), streams[n], n)
        else:
            match = re.search(r'<source [^ ]*[ ]*src="([^"]+)" ', self.get_urldata()[1])
            if not match:
                log.error("Can't find video info for: %s", self.url)
                return
            m3u8_url = match.group(1)
            options.live = checklive(m3u8_url)
            yield HLS(copy.copy(options), m3u8_url, 800)

def checklive(url):
    return True if re.search("live", url) else False