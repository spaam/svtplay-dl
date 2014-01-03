# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import json

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data

from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hls import download_hls
from svtplay_dl.fetcher.http import download_http

from svtplay_dl.log import log

class Radioplay(Service):
    supported_domains = ['radioplay.se']

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r"liveStationsRedundancy = ({.*});</script>", data)
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
