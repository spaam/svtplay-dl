# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.utils.urllib import urljoin
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.log import log
from svtplay_dl.subtitle import subtitle

class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ['urplay.se', 'ur.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return
        match = re.search(r"urPlayer.init\((.*)\);", data)
        if not match:
            log.error("Can't find json info")
            return

        if self.exclude(options):
            return

        data = match.group(1)
        jsondata = json.loads(data)
        yield subtitle(copy.copy(options), "tt", jsondata["subtitles"][0]["file"].split(",")[0])
        basedomain = jsondata["streaming_config"]["streamer"]["redirect"]
        http = "http://%s/%s" % (basedomain, jsondata["file_http"])
        hd = None
        if len(jsondata["file_http_hd"]) > 0:
            http_hd = "http://%s/%s" % (basedomain, jsondata["file_http_hd"])
            hls_hd = "%s%s" % (http_hd, jsondata["streaming_config"]["http_streaming"]["hls_file"])
            tmp = jsondata["file_http_hd"]
            match = re.search(".*(mp[34]:.*$)", tmp)
            path_hd = match.group(1)
            hd = True
        hls = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        rtmp = "rtmp://%s/%s" % (basedomain, jsondata["streaming_config"]["rtmp"]["application"])
        path = "mp%s:%s" % (jsondata["file_rtmp"][-1], jsondata["file_rtmp"])
        streams = hlsparse(hls)
        for n in list(streams.keys()):
            yield HLS(options, streams[n], n)
        options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], path)
        yield RTMP(options, rtmp, "480")
        if hd:
            streams = hlsparse(hls_hd)
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
            options.other = "-v -a %s -y %s" % (jsondata["streaming_config"]["rtmp"]["application"], path_hd)
            yield RTMP(copy.copy(options), rtmp, "720")

    def scrape_episodes(self, options):
        res = []
        for relurl in re.findall(r'<a class="puff tv video"\s+title="[^"]*"\s+href="([^"]*)"',
                                 self.get_urldata()[1]):
            res.append(urljoin(self.url, relurl.replace("&amp;", "&")))

        if options.all_last != -1:
            res = res[-options.all_last:]

        return res

    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata()[1])
        if match is None:
            log.info("Couldn't retrieve episode list as rss, trying to scrape")
            return self.scrape_episodes(options)

        url = "http://urplay.se%s" % match.group(1).replace("&amp;", "&")
        xml = ET.XML(get_http_data(url)[1])

        episodes = [x.text for x in xml.findall(".//item/link")]
        episodes_new = []
        n = 0
        for i in episodes:
            if n == options.all_last:
                break
            episodes_new.append(i)
            n += 1
        return episodes_new
