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

        match_cfg_url = re.search('data-config-url="([^"]+)" data-fallback-url', data)
        match_clip_page_cfg = re.search(r'vimeo\.clip_page_config\s*=\s*({.+?});', data)

        if match_cfg_url:
            player_url = match_cfg_url.group(1).replace("&amp;", "&")
        elif match_clip_page_cfg:
            page_config = json.loads(match_clip_page_cfg.group(1))
            player_url = page_config["player"]["config_url"]
        else:
            yield ServiceError("Can't find video file for: {0}".format(self.url))
            return

        player_data = self.http.request("get", player_url).text

        if player_data:

            jsondata = json.loads(player_data)

            if ("hls" in jsondata["request"]["files"]) and ("fastly_skyfire" in jsondata["request"]["files"]["hls"]["cdns"]):
                hls_elem = jsondata["request"]["files"]["hls"]["cdns"]["fastly_skyfire"]
                stream = hlsparse(self.config, self.http.request("get", hls_elem["url"]), hls_elem["url"], output=self.output)

                if stream:
                    for n in list(stream.keys()):
                        yield stream[n]

            avail_quality = jsondata["request"]["files"]["progressive"]
            for i in avail_quality:
                yield HTTP(copy.copy(self.config), i["url"], i["height"], output=self.output)
        else:
            yield ServiceError("Can't find any streams.")
            return
