# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import json
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Vimeo(Service, OpenGraphThumbMixin):
    supported_domains = ['vimeo.com']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match_cfg_url = re.search('data-config-url="([^"]+)" data-fallback-url', data)
        match_clip_page_cfg = re.search( r'vimeo\.clip_page_config\s*=\s*({.+?});', data)

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
            avail_quality = jsondata["request"]["files"]["progressive"]
            for i in avail_quality:
                yield HTTP(copy.copy(self.options), i["url"], i["height"])
        else:
            yield ServiceError("Can't find any streams.")
            return
