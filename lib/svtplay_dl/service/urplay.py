# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import sys

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, subtitle_tt
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hls import download_hls
from svtplay_dl.log import log

class Urplay(Service):
    supported_domains = ['urplay.se', 'ur.se']

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r"urPlayer.init\((.*)\);", data)
        if not match:
            log.error("Can't find json info")
            sys.exit(2)
        data = match.group(1)
        jsondata = json.loads(data)
        subtitle = jsondata["subtitles"].split(",")[0]
        basedomain = jsondata["streaming_config"]["streamer"]["redirect"]
        http = "http://%s/%s" % (basedomain, jsondata["file_html5"])
        hd = None
        if len(jsondata["file_html5_hd"]) > 0:
            http_hd = "http://%s/%s" % (basedomain, jsondata["file_html5_hd"])
            hls_hd = "%s%s" % (http_hd, jsondata["streaming_config"]["http_streaming"]["hls_file"])
            path_hd = "mp%s:%s" % (jsondata["file_hd"][-1], jsondata["file_hd"])
            hd = True
        #hds = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hds_file"])
        hls = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        rtmp = "rtmp://%s/%s" % (basedomain, jsondata["streaming_config"]["rtmp"]["application"])
        path = "mp%s:%s" % (jsondata["file_flash"][-1], jsondata["file_flash"])
        available = {"sd":{"hls":{"http":http, "playlist":hls}, "rtmp":{"server":rtmp, "path":path}}}
        if hd:
            available.update({"hd":{"hls":{"http":http_hd, "playlist":hls_hd}, "rtmp":{"server":rtmp, "path":path_hd}}})

        if options.quality:
            try:
                selected = available[options.quality]
            except KeyError:
                log.error("Can't find that quality. (Try one of: %s)",
                          ", ".join([str(elm) for elm in available]))
                sys.exit(4)
        else:
            try:
                selected = self.select_highest_quality(available)
            except KeyError:
                log.error("Can't find any streams.")
                sys.exit(4)

        options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], selected["rtmp"]["path"])
        if options.hls:
            download_hls(options, selected["hls"]["playlist"], selected["hls"]["http"])
        else:
            download_rtmp(options, selected["rtmp"]["server"])
        if options.subtitle:
            if options.output != "-":
                data = get_http_data(subtitle)
                subtitle_tt(options, data)

    def select_highest_quality(self, available):
        if 'hd' in available:
            return available["hd"]
        elif 'sd' in available:
            return available["sd"]
        else:
            raise KeyError()