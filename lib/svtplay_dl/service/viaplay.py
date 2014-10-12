# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET
import json
import copy

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.subtitle import subtitle_sami

class Viaplay(Service, OpenGraphThumbMixin):
    supported_domains = [
        'tv3play.se', 'tv6play.se', 'tv8play.se', 'tv10play.se',
        'tv3play.no', 'tv3play.dk', 'tv6play.no', 'viasat4play.no',
        'tv3play.ee', 'tv3play.lv', 'tv3play.lt', 'tvplay.lv', 'viagame.com']

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
        html_data = self.get_urldata()
        match = re.search(r'data-video-id="([0-9]+)"', html_data)
        if match:
            return match.group(1)
        match = re.search(r'data-videoid="([0-9]+)', html_data)
        if match:
            return match.group(1)

        parse = urlparse(self.url)
        match = re.search(r'/\w+/(\d+)', parse.path)
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
        error = xml.find("Error")
        if error is not None:
            log.error("%s" % error.text)
            return
        live = xml.find("Product").find("LiveInfo")
        if live is not None:
            live = live.find("Live").text
            if live == "true":
                options.live = True

        if xml.find("Product").find("SamiFile").text:
            yield subtitle_sami(xml.find("Product").find("SamiFile").text)

        # Fulhack.. expose error code from get_http_data.
        filename = xml.find("Product").find("Videos").find("Video").find("Url").text
        if filename[:4] != "rtmp":
            if filename[len(filename)-3:] == "f4m":
                filename = "%s?hdcore=2.8.0&g=hejsan" % filename
            filedata = get_http_data(filename)
            geoxml = ET.XML(filedata)
            if geoxml.find("Success") is not None:
                if geoxml.find("Success").text == "false":
                    log.error("Can't download file:")
                    log.error(xml.find("Msg").text)
                    sys.exit(2)

        streams = get_http_data("http://playapi.mtgx.tv/v1/videos/stream/%s" % vid)
        streamj = json.loads(streams)

        if streamj["streams"]["medium"]:
            filename = streamj["streams"]["medium"]
            if filename[len(filename)-3:] == "f4m":
                manifest = "%s?hdcore=2.8.0&g=hejsan" % filename
                streams = hdsparse(copy.copy(options), manifest)
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
            else:
                parse = urlparse(filename)
                match = re.search("^(/[^/]+)/(.*)", parse.path)
                if not match:
                    log.error("Somthing wrong with rtmpparse")
                    sys.exit(2)
                filename = "%s://%s:%s%s" % (parse.scheme, parse.hostname, parse.port, match.group(1))
                path = "-y %s" % match.group(2)
                options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf %s" % path
                yield RTMP(copy.copy(options), filename, 800)

        if streamj["streams"]["hls"]:
            streams = hlsparse(streamj["streams"]["hls"])
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)

    def find_all_episodes(self, options):
        format_id = re.search(r'data-format-id="(\d+)"', self.get_urldata())
        if not format_id:
            log.error("Can't find video info")
            sys.exit(2)
        data = get_http_data("http://playapi.mtgx.tv/v1/sections?sections=videos.one,seasons.videolist&format=%s" % format_id.group(1))
        jsondata = json.loads(data)
        videos = jsondata["_embedded"]["sections"][1]["_embedded"]["seasons"][0]["_embedded"]["episodelist"]["_embedded"]["videos"]

        return sorted(x["sharing"]["url"] for x in videos)
