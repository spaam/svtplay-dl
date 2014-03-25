# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET
import json

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


    def _get_video_id(self):
        """
        Extract video id. It will try to avoid making an HTTP request
        if it can find the ID in the URL, but otherwise it will try
        to scrape it from the HTML document. Returns None in case it's
        unable to extract the ID at all.
        """
        parse = urlparse(self.url)
        match = re.search(r'\/(\d+)/?', parse.path)
        if match:
            return match.group(1)

        html_data = self.get_urldata()
        match = re.search(r'data-link="[^"]+/([0-9]+)"', html_data)
        if match:
            return match.group(1)

        return None


    def get(self, options):
        vid = self._get_video_id()
        if vid is None:
            log.error("Cant find video file")
            sys.exit(2)

        url = "http://viastream.viasat.tv/PlayProduct/%s" % vid
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
        filename = "%s://%s:%s%s" % (parse.scheme, parse.hostname, parse.port, match.group(1))
        path = "-y %s" % match.group(2)
        options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf %s" % path
        if options.subtitle and options.force_subtitle:
            return

        download_rtmp(options, filename)

    def get_subtitle(self, options):
        if self.subtitle:
            data = get_http_data(self.subtitle)
            subtitle_sami(options, data)

    def find_all_episodes(self, options):
        format_id = re.search(r'data-format-id="(\d+)"', self.get_urldata())
        if not format_id:
            log.error("Can't find video info")
            sys.exit(2)
        data = get_http_data("http://playapi.mtgx.tv/v1/sections?sections=videos.one,seasons.videolist&format=%s" % format_id.group(1))
        jsondata = json.loads(data)
        videos = jsondata["_embedded"]["sections"][1]["_embedded"]["seasons"][0]["_embedded"]["episodelist"]["_embedded"]["videos"]

        return sorted(x["sharing"]["url"] for x in videos)
