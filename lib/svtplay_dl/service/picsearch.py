# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ["dn.se", "mobil.dn.se", "di.se", "csp.picsearch.com", "csp.screen9.com", "cdn.screen9.com"]
    backupapi = None

    def get(self):
        mediaid = self.get_mediaid()
        if not mediaid:
            yield ServiceError("Cant find media id")
            return
        mediaid = mediaid.group(1)

        jsondata = self.http.request("get", f"https://api.screen9.com/player/config/{mediaid}").text
        jsondata = json.loads(jsondata)

        for i in jsondata["src"]:
            if "application/x-mpegURL" in i["type"]:
                yield from hlsparse(
                    self.config,
                    self.http.request("get", i["src"]),
                    i["src"],
                    output=self.output,
                )

    def get_mediaid(self):
        match = re.search(r'media-id="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search(r'"mediaid": "([^"]+)"', self.get_urldata())
        return match
