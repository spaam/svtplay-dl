# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import decode_html_entities
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse


class Aftonbladettv(Service):
    supported_domains = ['tv.aftonbladet.se', "svd.se"]

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        apiurl = None
        match = re.search('data-player-config="([^"]+)"', data)
        if not match:
            match = re.search('data-svpPlayer-video="([^"]+)"', data)
            if not match:
                yield ServiceError("Can't find video info")
                return
        data = json.loads(decode_html_entities(match.group(1)))
        videoId = data["playerOptions"]["id"]
        apiurl = data["playerOptions"]["api"]
        vendor = data["playerOptions"]["vendor"]
        self.options.live = data["live"]
        if not self.options.live:
            dataurl = "{0}{1}/assets/{2}?appName=svp-player".format(apiurl, vendor, videoId)
            data = self.http.request("get", dataurl).text
            data = json.loads(data)

        streams = hlsparse(self.options, self.http.request("get", data["streamUrls"]["hls"]), data["streamUrls"]["hls"])
        if streams:
            for n in list(streams.keys()):
                yield streams[n]

class Aftonbladet(Service):
    supported_domains = ["aftonbladet.se"]


    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search('window.FLUX_STATE = ({.*})</script>', data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        janson = json.loads(match.group(1))
        articleid = janson["article"]["currentArticleId"]
        components = janson["articles"][articleid]["article"]["components"]
        for i in components:
            if "components" in i:
                for n in i["components"]:
                    if "type" in n and n["type"] == "video":
                        streams = hlsparse(self.options, self.http.request("get", n["videoAsset"]["streamUrls"]["hls"]),
                                               n["videoAsset"]["streamUrls"]["hls"])
                        if streams:
                            for n in list(streams.keys()):
                                yield streams[n]
