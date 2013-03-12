# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re

from svtplay.utils import get_http_data
from svtplay.fetcher.hls import download_hls

class Ruv(object):
    def handle(self, url):
        return "ruv.is" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'(http://load.cache.is/vodruv.*)"', data)
        js_url = match.group(1)
        js = get_http_data(js_url)
        tengipunktur = js.split('"')[1]
        match = re.search(r"http.*tengipunktur [+] '([:]1935.*)'", data)
        m3u8_url = "http://" + tengipunktur + match.group(1)
        base_url = m3u8_url.rsplit("/", 1)[0]
        download_hls(options, m3u8_url, base_url)

