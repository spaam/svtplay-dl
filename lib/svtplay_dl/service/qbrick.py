# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import is_py2_old
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.rtmp import RTMP


class Qbrick(Service, OpenGraphThumbMixin):
    supported_domains = ['di.seXX']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        if re.findall(r"di.se", self.url):
            match = re.search("src=\"(http://qstream.*)\"></iframe", data)
            if not match:
                yield ServiceError("Can't find video info for: %s" % self.url)
                return
            data = self.http.request("get", match.group(1)).content
            match = re.search(r"data-qbrick-ccid=\"([0-9A-Z]+)\"", data)
            if not match:
                yield ServiceError("Can't find video file for: %s" % self.url)
                return
            host = "http://vms.api.qbrick.com/rest/v3/getplayer/%s" % match.group(1)
        else:
            yield ServiceError("Can't find any info for %s" % self.url)
            return

        data = self.http.request("get", host).content
        xml = ET.XML(data)
        try:
            url = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            yield ServiceError("Can't find video file")
            return
        live = xml.find("media").find("item").find("playlist").find("stream").attrib["isLive"]
        if live == "true":
            self.options.live = True
        data = self.http.request("get", url).content
        xml = ET.XML(data)
        server = xml.find("head").find("meta").attrib["base"]
        streams = xml.find("body").find("switch")
        if is_py2_old:
            sa = list(streams.getiterator("video"))
        else:
            sa = list(streams.iter("video"))

        for i in sa:
            self.options.other = "-y '%s'" % i.attrib["src"]
            yield RTMP(copy.copy(self.options), server, i.attrib["system-bitrate"])
