# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
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
        data = self.get_urldata()
        match = re.search(r'video url-([^"]+)', data)
        if not match:
            match = re.search(r'embed.jsp\?id=([^&]+)&', data)
            if not match:
                log.error("Cant find video id")
                sys.exit(2)
            vid = match.group(1)
        if not vid:
            path = unquote_plus(match.group(1))
            data = get_http_data("http://www.svd.se%s" % path)
            match = re.search(r'embed.jsp\?id=([^&]+)&', data)
            if not match:
                log.error("Cant find video id2")
                sys.exit(2)
            vid = match.group(1)

        url = "http://amz.lwcdn.com/api/cache/VideoCache.jsp?id=%s" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        videofile = xml.find("{http://www.lemonwhale.com/xml11}VideoFile")
        mediafiles = videofile.find("{http://www.lemonwhale.com/xml11}MediaFiles")
        high = mediafiles.find("{http://www.lemonwhale.com/xml11}VideoURLHigh")
        if high.text:
            yield HTTP(copy.copy(options), high.text, 720)
        videourl = mediafiles.find(
            "{http://www.lemonwhale.com/xml11}VideoURL").text
        yield HTTP(copy.copy(options), videourl, 480)
