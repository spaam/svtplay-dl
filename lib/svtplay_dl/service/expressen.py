# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.error import ServiceError
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils import decode_html_entities


class Expressen(Service):
    supported_domains = ['expressen.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search('="(https://www.expressen.se/tvspelare[^"]+)"', data)
        if not match:
            log.error("Can't find video id")
            return
        url = decode_html_entities(match.group(1))
        data = self.http.request("get", url)

        match = re.search("window.Player.settings = ({.*});", data.text)
        if not match:
            log.error("Can't find json info.")

        dataj = json.loads(match.group(1))
        if "streams" in dataj:
            if "iPad" in dataj["streams"]:
                streams = hlsparse(self.options, self.http.request("get", dataj["streams"]["iPad"]), dataj["streams"]["iPad"])
                for n in list(streams.keys()):
                    yield streams[n]
            if "hashHls" in dataj["streams"]:
                streams = hlsparse(self.options, self.http.request("get", dataj["streams"]["hashHls"]), dataj["streams"]["hashHls"])
                for n in list(streams.keys()):
                    yield streams[n]
