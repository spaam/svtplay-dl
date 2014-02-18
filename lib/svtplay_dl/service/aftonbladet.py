# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import download_hls

class Aftonbladet(Service):
    supported_domains = ['tv.aftonbladet.se']

    def get(self, options):
        data = self.get_urldata()
        match = re.search('data-aptomaId="([-0-9a-z]+)"', data)
        if not match:
            log.error("Can't find video info")
            sys.exit(2)
        videoId = match.group(1)
        match = re.search(r'data-isLive="(\w+)"', data)
        if not match:
            log.error("Can't find live info")
            sys.exit(2)
        if match.group(1) == "true":
            options.live = True
        if not options.live:
            dataurl = "http://aftonbladet-play-metadata.cdn.drvideo.aptoma.no/video/%s.json" % videoId
            data = get_http_data(dataurl)
            data = json.loads(data)
            videoId = data["videoId"]

        streamsurl = "http://aftonbladet-play-static-ext.cdn.drvideo.aptoma.no/actions/video/?id=%s&formats&callback=" % videoId
        streams = json.loads(get_http_data(streamsurl))
        hls = streams["formats"]["hls"]["level3"]["m3u8"][0]
        playlist = "http://%s/%s/%s" % (hls["address"], hls["path"], hls["filename"])
        download_hls(options, playlist)
