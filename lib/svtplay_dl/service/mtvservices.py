# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, is_py2_old
from svtplay_dl.fetcher.http import HTTP

from svtplay_dl.log import log

class Mtvservices(Service):
    supported_domains = ['colbertnation.com', 'thedailyshow.com']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Cant get page")
            return
        match = re.search(r"mgid=\"(mgid.*[0-9]+)\" data-wi", data)
        if not match:
            log.error("Can't find video file")
            return
        url = "http://media.mtvnservices.com/player/html5/mediagen/?uri=%s" % match.group(1)
        error, data = get_http_data(url)
        if error:
            log.error("Cant get stream info")
            return
        start = data.index("<?xml version=")
        data = data[start:]
        xml = ET.XML(data)
        ss = xml.find("video").find("item")
        if is_py2_old:
            sa = list(ss.getiterator("rendition"))
        else:
            sa = list(ss.iter("rendition"))

        if self.exclude(options):
            return

        for i in sa:
            temp = i.find("src").text.index("gsp.comedystor")
            url = "http://mtvnmobile.vo.llnwd.net/kip0/_pxn=0+_pxK=18639+_pxE=mp4/44620/mtvnorigin/%s" % i.find("src").text[temp:]
            yield HTTP(copy.copy(options), url, i.attrib["height"])
