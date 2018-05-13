# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import json
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError

from svtplay_dl.fetcher.hls import hlsparse


class Vimeo(Service, OpenGraphThumbMixin):
    supported_domains = ['vimeo.com']

    def get(self):
        data = self.get_urldata()

        match = re.search('data-config-url="([^"]+)" data-fallback-url', data)
        if not match:
            yield ServiceError("Can't find video file for: {0}".format(self.url))
            return

        player_data = self.http.request("get", player_url).text

        if player_data:

            jsondata = json.loads(player_data)

            if ("hls" in jsondata["request"]["files"]) and ("fastly_skyfire" in jsondata["request"]["files"]["hls"]["cdns"]):
                hls_elem = jsondata["request"]["files"]["hls"]["cdns"]["fastly_skyfire"]
                stream = hlsparse(self.options, self.http.request("get", hls_elem["url"]), hls_elem["url"])

                if stream:
                    for n in list(stream.keys()):
                        yield stream[n]

            avail_quality = jsondata["request"]["files"]["progressive"]
            for i in avail_quality:
                yield HTTP(copy.copy(self.config), i["url"], i["height"])
        else:
            yield ServiceError("Can't find any streams.")
            return
