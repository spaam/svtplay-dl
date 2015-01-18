# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.log import log

class Nrk(Service, OpenGraphThumbMixin):
    supported_domains = ['nrk.no', 'tv.nrk.no']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return

        if self.exclude(options):
            return

        match = re.search("data-subtitlesurl = \"(/.*)\"", data)

        if match:
            parse = urlparse(self.url)
            suburl = "%s://%s%s" % (parse.scheme, parse.netloc, match.group(1))
            yield subtitle(copy.copy(options), "tt", suburl)

        if options.force_subtitle:
            return

        match = re.search(r'data-media="(.*manifest.f4m)"', self.get_urldata()[1])
        if match:
            manifest_url = match.group(1)
        else:
            match = re.search(r'data-video-id="(\d+)"', self.get_urldata()[1])
            if match is None:
                log.error("Can't find video id.")
                return
            vid = match.group(1)
            match = re.search(r"PS_VIDEO_API_URL : '([^']*)',", self.get_urldata()[1])
            if match is None:
                log.error("Can't find server address with media info")
                return
            dataurl = "%smediaelement/%s" % (match.group(1), vid)
            error, data = get_http_data(dataurl)
            data = json.loads(data)
            manifest_url = data["mediaUrl"]
            options.live = data["isLive"]

        hlsurl = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        streams = hlsparse(hlsurl)
        for n in list(streams.keys()):
            yield HLS(copy.copy(options), streams[n], n)

        streams = hdsparse(copy.copy(options), manifest_url)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]
