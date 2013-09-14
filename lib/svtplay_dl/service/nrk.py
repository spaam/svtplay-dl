# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, subtitle_tt
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hds import download_hds
from svtplay_dl.fetcher.hls import download_hls

class Nrk(Service):
    def handle(self, url):
        return "nrk.no" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'data-media="(.*manifest.f4m)"', data)
        manifest_url = match.group(1)
        if options.hls:
            manifest_url = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
            download_hls(options, manifest_url)
        else:
            manifest_url = "%s?hdcore=2.8.0&g=hejsan" % manifest_url
            download_hds(options, manifest_url)
        if options.subtitle:
            match = re.search("data-subtitlesurl = \"(/.*)\"", data)
            if match:
                parse = urlparse(url)
                subtitle = "%s://%s%s" % (parse.scheme, parse.netloc, match.group(1))
                data = get_http_data(subtitle)
                subtitle_tt(options, data)

