# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import sys
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.log import log
from svtplay_dl.subtitle import subtitle_tt

class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ['urplay.se', 'ur.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        match = re.search(r"urPlayer.init\((.*)\);", self.get_urldata())
        if not match:
            log.error("Can't find json info")
            sys.exit(2)
        data = match.group(1)
        jsondata = json.loads(data)
        yield subtitle_tt(jsondata["subtitles"].split(",")[0])
        basedomain = jsondata["streaming_config"]["streamer"]["redirect"]
        http = "http://%s/%s" % (basedomain, jsondata["file_html5"])
        hd = None
        if len(jsondata["file_html5_hd"]) > 0:
            http_hd = "http://%s/%s" % (basedomain, jsondata["file_html5_hd"])
            hls_hd = "%s%s" % (http_hd, jsondata["streaming_config"]["http_streaming"]["hls_file"])
            tmp = jsondata["file_html5_hd"]
            match = re.search(".*(mp[34]:.*$)", tmp)
            path_hd = match.group(1)
            hd = True
        hls = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        rtmp = "rtmp://%s/%s" % (basedomain, jsondata["streaming_config"]["rtmp"]["application"])
        path = "mp%s:%s" % (jsondata["file_flash"][-1], jsondata["file_flash"])
        streams = hlsparse(hls)
        for n in list(streams.keys()):
            yield HLS(options, streams[n], n)
        options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], path)
        yield RTMP(options, rtmp, "480")
        if hd:
            streams = hlsparse(hls_hd)
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
            options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], path_hd)
            yield RTMP(copy.copy(options), rtmp, "720")

    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
        if match is None:
            log.error("Couldn't retrieve episode list")
            sys.exit(2)
        url = "http://urplay.se%s" % match.group(1).replace("&amp;", "&")
        xml = ET.XML(get_http_data(url))

        return sorted(x.text for x in xml.findall(".//item/link"))