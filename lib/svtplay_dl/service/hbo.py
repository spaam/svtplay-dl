# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp

class Hbo(Service):
    def handle(self, url):
        return "hbo.com" in url

    def get(self, options, url):
        parse = urlparse(url)
        try:
            other = parse[5]
        except KeyError:
            log.error("Something wrong with that url")
            sys.exit(2)
        match = re.search("^/(.*).html", other)
        if not match:
            log.error("Cant find video file")
            sys.exit(2)
        url = "http://www.hbo.com/data/content/%s.xml" % match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        videoid = xml.find("content")[1].find("videoId").text
        url = "http://render.cdn.hbo.com/data/content/global/videos/data/%s.xml" % videoid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("videos")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("size"))
        else:
            sa = list(ss.iter("size"))
        streams = {}
        for i in sa:
            stream = {}
            stream["path"] = i.find("tv14").find("path").text
            streams[int(i.attrib["width"])] = stream

        test = select_quality(options, streams)

        download_rtmp(options, test["path"])

