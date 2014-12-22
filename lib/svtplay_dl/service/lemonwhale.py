# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import unquote_plus
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.http import HTTP

class Lemonwhale(Service):
    supported_domains = ['svd.se']

    def get(self, options):
        vid = None
        error, data = self.get_urldata()
        if error:
            log.error("Can't get data from that page")
            return

        if self.exclude(options):
            return

        match = re.search(r'video url-([^"]+)', data)
        if not match:
            match = re.search(r'embed.jsp\?([^"]+)"', self.get_urldata()[1])
            if not match:
                log.error("Can't find video id")
                return
            vid = match.group(1)
        if not vid:
            path = unquote_plus(match.group(1))
            error, data = get_http_data("http://www.svd.se%s" % path)
            match = re.search(r'embed.jsp\?([^"]+)', data)
            if not match:
                log.error("Can't find video id")
                return
            vid = match.group(1)

        url = "http://amz.lwcdn.com/api/cache/VideoCache.jsp?%s" % vid
        error, data = get_http_data(url)
        if error:
            log.error("Cant download video info")
            return
        xml = ET.XML(data)
        videofile = xml.find("{http://www.lemonwhale.com/xml11}VideoFile")
        mediafiles = videofile.find("{http://www.lemonwhale.com/xml11}MediaFiles")
        high = mediafiles.find("{http://www.lemonwhale.com/xml11}VideoURLHigh")
        if high.text:
            yield HTTP(copy.copy(options), high.text, 720)
        videourl = mediafiles.find(
            "{http://www.lemonwhale.com/xml11}VideoURL").text
        yield HTTP(copy.copy(options), videourl, 480)
