# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality, is_py2_old
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP

from svtplay_dl.utils.urllib import quote_plus

class Expressen(Service):
    supported_domains = ['expressen.se']

    def get(self, options):
        match = re.search(r"xmlUrl: '(http://www.expressen.*)'", self.get_urldata())
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://tv.expressen.se/%s/?standAlone=true&output=xml" % quote_plus(match.group(1))
        url = match.group(1)
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("vurls")
        if is_py2_old:
            sa = list(ss.getiterator("vurl"))
        else:
            sa = list(ss.iter("vurl"))

        for i in sa:
            match = re.search(r"rtmp://([0-9a-z\.]+/[0-9]+/)(.*)", i.text)
            filename = "rtmp://%s" % match.group(1)
            options.other = "-y %s" % match.group(2)
            yield RTMP(options, filename, i.attrib["bitrate"])

