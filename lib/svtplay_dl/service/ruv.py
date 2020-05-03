# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import HLS
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import Service


class Ruv(Service):
    supported_domains = ["ruv.is"]

    def get(self):
        data = self.get_urldata()

        match = re.search(r'"([^"]+geo.php)"', data)
        if match:
            data = self.http.request("get", match.group(1)).content
            match = re.search(r"punktur=\(([^ ]+)\)", data)
            if match:
                janson = json.loads(match.group(1))
                self.config.get("live", checklive(janson["result"][1]))
                streams = hlsparse(self.config, self.http.request("get", janson["result"][1]), janson["result"][1], output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]
            else:
                yield ServiceError("Can't find json info")
        else:
            match = re.search(r'<source [^ ]*[ ]*src="([^"]+)" ', self.get_urldata())
            if not match:
                yield ServiceError("Can't find video info for: %s" % self.url)
                return
            if match.group(1).endswith("mp4"):
                yield HTTP(copy.copy(self.config), match.group(1), 800, output=self.output)
            else:
                m3u8_url = match.group(1)
                self.config.set("live", checklive(m3u8_url))
                yield HLS(copy.copy(self.config), m3u8_url, 800, output=self.output)


def checklive(url):
    return True if re.search("live", url) else False
