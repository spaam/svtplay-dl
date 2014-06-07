# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import json
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.log import log

class Vimeo(Service, OpenGraphThumbMixin):
    supported_domains = ['vimeo.com']

    def get(self, options):
        match = re.search("data-config-url=\"(.*)\" data-fallback-url", self.get_urldata())
        if not match:
            log.error("Can't find data")
            sys.exit(4)
        player_url = match.group(1).replace("&amp;", "&")
        player_data = get_http_data(player_url)

        if player_data:
            jsondata = json.loads(player_data)
            avail_quality = jsondata["request"]["files"]["h264"]
            for i in avail_quality.keys():
                yield HTTP(copy.copy(options), avail_quality[i]["url"], avail_quality[i]["bitrate"])
        else:
            log.error("Can't find any streams.")
            sys.exit(2)