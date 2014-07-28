# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import json
import copy

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import HLS, hlsparse

class Vhx(Service):
    supported_domains = ['embed.vhx.tv']

    def get_urldata(self):
        if self._urldata is None:
            self._urldata = get_http_data(self.url)
        return self._urldata

    def get(self, options):
        log.debug('Using VHX handler')
        try:
            video_id = self.url.split('vhx.tv/videos/')[1].split('?')[0]
            log.debug("Video ID: {}".format(video_id))
        except IndexError:
            # Rudimentary error check
            log.error("Error parsing URL")
            sys.exit(2)
        methods_url = 'https://embed.vhx.tv/videos/{}/files'.format(video_id)
        streaming_methods = get_http_data(methods_url)
        js = json.loads(streaming_methods)
        playlist = js['hls']

        streams = hlsparse(playlist)
        for bitrate, url in streams.items():
            yield HLS(copy.copy(options), url, bitrate)
