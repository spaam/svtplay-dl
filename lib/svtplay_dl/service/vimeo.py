# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import json
import re

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.http import download_http
from svtplay_dl.log import log

class Vimeo(Service):
    supported_domains = ['vimeo.com']

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search("data-config-url=\"(.*)\" data-fallback-url", data)
        if not match:
            log.error("Can't find data")
            sys.exit(4)
        player_url = match.group(1).replace("&amp;", "&")
        player_data = get_http_data(player_url)

        if player_data:
            jsondata = json.loads(player_data)
            avail_quality = jsondata["request"]["files"]["h264"]
            if options.quality:
                try:
                    selected = avail_quality[options.quality]
                except KeyError:
                    log.error("Can't find that quality. (Try one of: %s)",
                              ", ".join([str(elm) for elm in avail_quality]))
                    sys.exit(4)
            else:
                try:
                    selected = self.select_highest_quality(avail_quality)
                except KeyError:
                    log.error("Can't find any streams.")
                    sys.exit(4)
            url = selected['url']
            download_http(options, url)
        else:
            log.error("Can't find any streams.")
            sys.exit(2)

    def select_highest_quality(self, available):
        if 'hd' in available:
            return available['hd']
        elif 'sd' in available:
            return available['sd']
        else:
            raise KeyError()
