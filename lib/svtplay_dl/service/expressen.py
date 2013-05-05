# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp

from svtplay_dl.utils.urllib import quote_plus

class Expressen(Service):
    def handle(self, url):
        return "expressen.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r"xmlUrl: '(http://www.expressen.*)'", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://tv.expressen.se/%s/?standAlone=true&output=xml" % quote_plus(match.group(1))
        url = match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("vurls")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("vurl"))
        else:
            sa = list(ss.iter("vurl"))
        streams = {}

        for i in sa:
            streams[int(i.attrib["bitrate"])] = i.text

        test = select_quality(options, streams)

        filename = test
        match = re.search(r"rtmp://([0-9a-z\.]+/[0-9]+/)(.*)", filename)

        filename = "rtmp://%s" % match.group(1)
        options.other = "-y %s" % match.group(2)

        download_rtmp(options, filename)

