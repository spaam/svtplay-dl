# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.http import download_http
from svtplay_dl.log import log

class Vimeo(Service):
    def handle(self, url):
        return "vimeo.com" in url

    def get(self, options, url):
        data = get_http_data(url, referer="")
        match = data.split(' = {config:')[1].split(',assets:')[0]
        if match:
            jsondata = json.loads(match)
            sig = jsondata['request']['signature']
            vidid = jsondata["video"]["id"]
            timestamp = jsondata['request']['timestamp']
            referer = jsondata["request"]["referrer"]
            avail_quality = jsondata["video"]["files"]["h264"]
            selected_quality = None
            for i in avail_quality:
                if options.quality == i:
                    selected_quality = i

            if options.quality and selected_quality is None:
                log.error("Can't find that quality. (Try one of: %s)",
                      ", ".join([str(elm) for elm in avail_quality]))
                sys.exit(4)
            elif options.quality is None and selected_quality is None:
                selected_quality = avail_quality[0]
            url = "http://player.vimeo.com/play_redirect?clip_id=%s&sig=%s&time=%s&quality=%s&codecs=H264,VP8,VP6&type=moogaloop_local&embed_location=%s" % (vidid, sig, timestamp, selected_quality, referer)
            download_http(options, url)
        else:
            log.error("Can't find any streams.")
            sys.exit(2)
