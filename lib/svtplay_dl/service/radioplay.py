# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import json

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service

from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hls import download_hls
from svtplay_dl.fetcher.http import download_http

from svtplay_dl.log import log

class Radioplay(Service):
    supported_domains = ['radioplay.se']

    def get(self, options):
        match = re.search(r"liveStationsRedundancy = ({.*});</script>", self.get_urldata())
        parse = urlparse(self.url)
        station = parse.path[1:]
        streams = None
        if match:
            data = json.loads(match.group(1))
            for i in data["stations"]:
                if station == i["name"].lower().replace(" ", ""):
                    streams = i["streams"]
                    break
        else:
            log.error("Can't find any streams.")
            sys.exit(2)
        if streams:
            if options.hls:
                try:
                    m3u8_url = streams["hls"]
                    download_hls(options, m3u8_url)
                except KeyError:
                    log.error("Can't find any streams.")
                    sys.exit(2)
            else:
                try:
                    rtmp = streams["rtmp"]
                    download_rtmp(options, rtmp)
                except KeyError:
                    mp3 = streams["mp3"]
                    download_http(options, mp3)

        else:
            log.error("Can't find any streams.")
            sys.exit(2)
