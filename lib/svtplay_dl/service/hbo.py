# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, is_py2_old
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP

class Hbo(Service):
    supported_domains = ['hbo.com']

    def get(self, options):
        parse = urlparse(self.url)
        try:
            other = parse.fragment
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
        if is_py2_old:
            sa = list(ss.getiterator("size"))
        else:
            sa = list(ss.iter("size"))

        for i in sa:
            videourl = i.find("tv14").find("path").text
            match = re.search("/([a-z0-9]+:[a-z0-9]+)/", videourl)
            options.other = "-y %s" % videourl[videourl.index(match.group(1)):]
            yield RTMP(copy.copy(options), videourl[:videourl.index(match.group(1))], i.attrib["width"])
