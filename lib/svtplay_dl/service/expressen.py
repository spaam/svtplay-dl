# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re

from svtplay_dl.service import Service
from svtplay_dl.error import UIException
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.http import HTTP

class ExpressenException(UIException):
    pass

class Expressen(Service):
    supported_domains = ['expressen.se']
    expressen_div_id = 'ctl00_WebTvArticleContent_BaseVideoHolder_VideoPlaceHolder_Satellite_Satellite'

    def _get_video_source(self, vtype):
        match = re.search(
            '<source src="([^"]+)" type="%s" />' % vtype, self.get_urldata()
        )

        if not match:
            raise ExpressenException(
                "Could not find any videos of type %s" % vtype)

        return match.group(1)

    def _get_hls(self):
        return self._get_video_source("application/x-mpegURL")

    def _get_mp4(self):
        return self._get_video_source('video/mp4')

    def get(self, options):
        try:
            try:
                url = self._get_hls()
                streams = hlsparse(url)
                for n in list(streams.keys()):
                    yield HLS(options, streams[n], n)
            except ExpressenException as exc:
                # Lower res, but static mp4 file.
                log.debug(exc)
                url = self._get_mp4()
                yield HTTP(options, url)
        except ExpressenException:
            log.error("Could not find any videos in '%s'", self.url)
