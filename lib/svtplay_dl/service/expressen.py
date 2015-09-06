# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.error import UIException
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.utils import is_py2_old
from svtplay_dl.utils.urllib import unquote_plus

class Expressen(Service):
    supported_domains = ['expressen.se']

    def get(self, options):
        data = self.get_urldata()

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        match = re.search("xmlUrl=([^ ]+)\" ", data)
        if match:
            xmlurl = unquote_plus(match.group(1))
        else:
            match = re.search(
                r"moviesList: \[\{\"VideoId\":\"(\d+)\"",
                self.get_urldata())
            if not match:
                log.error("Can't find video id")
                return
            vid = match.group(1)
            xmlurl = "http://www.expressen.se/Handlers/WebTvHandler.ashx?id=%s" % vid
        data = self.http.request("get", xmlurl).content

        xml = ET.XML(data)
        live = xml.find("live").text
        if live != "0":
            options.live = True
        ss = xml.find("vurls")
        if is_py2_old:
            sa = list(ss.getiterator("vurl"))
        else:
            sa = list(ss.iter("vurl"))

        for i in sa:
            options2 = copy.copy(options)
            match = re.search(r"rtmp://([-0-9a-z\.]+/[-a-z0-9]+/)(.*)", i.text)
            filename = "rtmp://%s" % match.group(1)
            options2.other = "-y %s" % match.group(2)
            yield RTMP(options2, filename, int(i.attrib["bitrate"]))

        ipadurl = xml.find("mobileurls").find("ipadurl").text
        streams = hlsparse(ipadurl, self.http.request("get", ipadurl).text)
        for n in list(streams.keys()):
            yield HLS(copy.copy(options), streams[n], n)
