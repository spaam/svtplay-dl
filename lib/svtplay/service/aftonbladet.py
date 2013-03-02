# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay.utils import get_http_data
from svtplay.log import log
from svtplay.rtmp import download_rtmp
from svtplay.http import download_http

if sys.version_info > (3, 0):
    from urllib.parse import urlparse, parse_qs
else:
    from urlparse import urlparse, parse_qs

class Aftonbladet():
    def handle(self, url):
        return "aftonbladet.se" in url

    def get(self, options, url):
        parse = urlparse(url)
        data = get_http_data(url)
        match = re.search("abTvArticlePlayer-player-(.*)-[0-9]+-[0-9]+-clickOverlay", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        try:
            start = parse_qs(parse[4])["start"][0]
        except KeyError:
            start = 0
        url = "http://www.aftonbladet.se/resource/webbtv/article/%s/player" % match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("articleElement").find("mediaElement").find("baseUrl").text
        path = xml.find("articleElement").find("mediaElement").find("media").attrib["url"]
        live = xml.find("articleElement").find("mediaElement").find("isLive").text
        options.other = "-y %s" % path

        if start > 0:
            options.other = "%s -A %s" % (options.other, str(start))

        if live == "true":
            options.live = True

        if url == None:
            log.error("Can't find any video on that page")
            sys.exit(3)

        if url[0:4] == "rtmp":
            download_rtmp(options, url)
        else:
            filename = url + path
            download_http(options, filename)

