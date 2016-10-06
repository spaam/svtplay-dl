# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import decode_html_entities
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse


class Aftonbladet(Service):
    supported_domains = ['tv.aftonbladet.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        apiurl = None
        match = re.search('data-player-config="([^"]+)"', data)
        if not match:
            yield ServiceError("Can't find video info")
            return
        janson = json.loads(decode_html_entities(match.group(1)))

        videoId = janson["playerOptions"]["id"]
        apiurl = janson["playerOptions"]["api"]
        vendor = janson["playerOptions"]["vendor"]
        self.options.live = janson["live"]
        if not self.options.live:
            dataurl = "{}{}/assets/{}?appName=svp-player".format(apiurl, vendor, videoId)
            data = self.http.request("get", dataurl).text
            data = json.loads(data)

            streams = hlsparse(self.options, self.http.request("get", data["streamUrls"]["hls"]), data["streamUrls"]["hls"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
