# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re

from svtplay.utils import get_http_data
from svtplay.rtmp import download_rtmp

class Urplay():
    def handle(self, url):
        return "urplay.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search('file=(.*)\&plugins', data)
        if match:
            path = "mp%s:%s" % (match.group(1)[-1], match.group(1))
            options.other = "-a ondemand -y %s" % path
            download_rtmp(options, "rtmp://streaming.ur.se/")

