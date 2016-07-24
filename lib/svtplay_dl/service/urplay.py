# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urljoin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.log import log
from svtplay_dl.error import ServiceError
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils import filenamify


class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ['urplay.se', 'ur.se', 'betaplay.ur.se', 'urskola.se']

    def get(self):
        data = self.get_urldata()
        match = re.search(r"urPlayer.init\((.*)\);", data)
        if not match:
            yield ServiceError("Can't find json info")
            return

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        data = match.group(1)
        jsondata = json.loads(data)
        if len(jsondata["subtitles"]) > 0:
            for sub in jsondata["subtitles"]:
                if "label" in sub:
                    if self.options.get_all_subtitles:
                        yield subtitle(copy.copy(self.options), "tt", sub["file"].split(",")[0], "-" + filenamify(sub["label"]))
                    else:
                        yield subtitle(copy.copy(self.options), "tt", sub["file"].split(",")[0])
                        
        if "streamer" in jsondata["streaming_config"]:
            basedomain = jsondata["streaming_config"]["streamer"]["redirect"]
        else:
            lbjson = self.http.request("get", jsondata["streaming_config"]["loadbalancer"]).text
            lbjson = json.loads(lbjson)
            basedomain = lbjson["redirect"]
        http = "http://%s/%s" % (basedomain, jsondata["file_http"])
        hd = None
        if len(jsondata["file_http_hd"]) > 0:
            http_hd = "http://%s/%s" % (basedomain, jsondata["file_http_hd"])
            hls_hd = "%s%s" % (http_hd, jsondata["streaming_config"]["http_streaming"]["hls_file"])
            hd = True
        hls = "%s%s" % (http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        streams = hlsparse(self.options, self.http.request("get", hls), hls)
        for n in list(streams.keys()):
            yield streams[n]
        if hd:
            streams = hlsparse(self.options, self.http.request("get", hls_hd), hls_hd)
            for n in list(streams.keys()):
                yield streams[n]

    def scrape_episodes(self, options):
        res = []
        for relurl in re.findall(r'<a class="puff tv video"\s+title="[^"]*"\s+href="([^"]*)"',
                                 self.get_urldata()):
            res.append(urljoin(self.url, relurl.replace("&amp;", "&")))

        for relurl in re.findall(r'<a class="card program"\s+href="([^"]*)"',
                                  self.get_urldata()):
            res.append(urljoin(self.url, relurl.replace("&amp;", "&")))

        if options.all_last != -1:
            res = res[-options.all_last:]

        return res

    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
        if match is None:
            log.info("Couldn't retrieve episode list as rss, trying to scrape")
            return self.scrape_episodes(options)

        url = "http://urplay.se%s" % match.group(1).replace("&amp;", "&")
        xml = ET.XML(self.http.request("get", url).content)

        episodes = [x.text for x in xml.findall(".//item/link")]
        episodes_new = []
        n = 0
        for i in episodes:
            if n == options.all_last:
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new
