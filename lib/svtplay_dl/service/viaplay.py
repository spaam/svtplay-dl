# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, subtitle_sami
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp

class Viaplay(Service, OpenGraphThumbMixin):
    supported_domains = [
        'tv3play.se', 'tv6play.se', 'tv8play.se', 'tv10play.se',
        'tv3play.no', 'tv3play.dk', 'tv6play.no', 'viasat4play.no',
        'tv3play.ee', 'tv3play.lv', 'tv3play.lt', 'tvplay.lv']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        parse = urlparse(self.url)
        match = re.search(r'\/(\d+)/?', parse.path)
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
        if xml.find("Product").find("Syndicate").text == "true":
            options.live = True
        filename = xml.find("Product").find("Videos").find("Video").find("Url").text
        self.subtitle = xml.find("Product").find("SamiFile").text

        if filename[:4] == "http":
            data = get_http_data(filename)
            xml = ET.XML(data)
            filename = xml.find("Url").text
            if xml.find("Msg").text:
                log.error("Can't download file:")
                log.error(xml.find("Msg").text)
                sys.exit(2)

        parse = urlparse(filename)
        match = re.search("^(/[a-z0-9]{0,20})/(.*)", parse.path)
        if not match:
            log.error("Somthing wrong with rtmpparse")
            sys.exit(2)
        filename = "%s://%s%s" % (parse.scheme, parse.hostname, match.group(1))
        path = "-y %s" % match.group(2)
        options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf %s" % path
        download_rtmp(options, filename)

    def get_subtitle(self, options):
        if self.subtitle:
            data = get_http_data(self.subtitle)
            subtitle_sami(options, data)
