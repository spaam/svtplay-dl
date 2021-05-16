# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service
from svtplay_dl.utils.text import decode_html_entities


class Expressen(Service):
    supported_domains = ["expressen.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search('data-article-data="([^"]+)"', data)
        if not match:
            yield ServiceError("Cant find video file info")
            return
        data = decode_html_entities(match.group(1))
        janson = json.loads(data)
        self.config.set("live", janson["isLive"])

        yield from hlsparse(self.config, self.http.request("get", janson["stream"]), janson["stream"], output=self.output)
