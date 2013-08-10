# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, subtitle_sami
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp

class Viaplay(Service):
    def handle(self, url):
        return ("tv3play.se" in url) or ("tv6play.se" in url) or ("tv8play.se" in url)

    def get(self, options, url):
        parse = urlparse(url)
        match = re.search(r'\/play\/(.*)/?', parse.path)
        if not match:
            log.error("Cant find video file")
            sys.exit(2)
        url = "http://viastream.viasat.tv/PlayProduct/%s" % match.group(1)
        options.other = ""
        data = get_http_data(url)
        xml = ET.XML(data)
        live = xml.find("Product").find("LiveInfo")
        if live is not None:
            live = live.find("Live").text
            if live == "true":
                options.live = True

        filename = xml.find("Product").find("Videos").find("Video").find("Url").text
        subtitle = xml.find("Product").find("SamiFile").text

        if filename[:4] == "http":
            data = get_http_data(filename)
            xml = ET.XML(data)
            filename = xml.find("Url").text

        options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf"
        download_rtmp(options, filename)
        if options.subtitle and subtitle:
            if options.output != "-":
                data = get_http_data(subtitle)
                subtitle_sami(options, data)
