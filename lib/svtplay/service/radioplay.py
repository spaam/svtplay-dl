from __future__ import absolute_import
import sys
import re
import json
from urlparse import urlparse

from svtplay.utils import get_http_data

from svtplay.fetcher.rtmp import download_rtmp
from svtplay.fetcher.hls import download_hls
from svtplay.fetcher.http import download_http

from svtplay.log import log

class Radioplay(object):
    def handle(self, url):
        return "radioplay.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search("liveStationsRedundancy = ({.*});</script>", data)
        parse = urlparse(url)
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
                    base_url = m3u8_url.rsplit("/", 1)[0]
                    download_hls(options, m3u8_url, base_url)
                except KeyError:
                    log.error("Can't find any streams.")
                    sys.error(2)
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
