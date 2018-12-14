# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import json
from datetime import datetime
from urllib.parse import urlparse

from svtplay_dl.service import Service
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse


class Atg(Service):
    supported_domains = ["atgplay.se"]

    def get(self):
        parse = urlparse(self.url)

        if not parse.path.startswith("/video"):
            yield ServiceError("Can't find video info")
            return

        wanted_id = parse.path[7:]
        current_time = int((datetime.utcnow() - datetime.utcfromtimestamp(0)).total_seconds() * 1000)

        api_url = "https://www.atgplay.se/api/{0}/video/{1}".format(current_time, wanted_id)
        video_assets = self.http.request("get", api_url)

        try:
            janson = json.loads(video_assets.text)
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {0}".format(video_assets.text))
            return

        if "title" in janson:
            self.output["title"] = janson["title"]

        if "urls" in janson:
            for i in janson["urls"]:
                if "m3u" == i:
                    stream = hlsparse(self.config, self.http.request("get", janson["urls"]["m3u"]), janson["urls"]["m3u"], output=self.output)

                    for key in list(stream.keys()):
                            yield stream[key]
