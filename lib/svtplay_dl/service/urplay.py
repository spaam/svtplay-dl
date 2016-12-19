# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urljoin, urlparse
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
                    absurl = urljoin(self.url, sub["file"].split(",")[0])
                    if absurl.endswith("vtt"):
                        subtype = "wrst"
                    else:
                        subtype = "tt"
                    if self.options.get_all_subtitles:
                        yield subtitle(copy.copy(self.options), subtype, absurl, "-" + filenamify(sub["label"]))
                    else:
                        yield subtitle(copy.copy(self.options), subtype, absurl)

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

    def find_all_episodes(self, options):
        parse = urlparse(self.url)
        match = re.search("/program/\d+-(\w+)-", parse.path)
        if not match:
            log.error("Can't find any videos")
            return None
        keyword = match.group(1)
        episodes = []
        all_links = re.findall('card-link" href="([^"]+)"', self.get_urldata())
        for i in all_links:
            match = re.search("/program/\d+-(\w+)-", i)
            if match and match.group(1) == keyword:
                episodes.append(urljoin("http://urplay.se/", i))

        episodes_new = []
        n = 0
        for i in episodes:
            if n == options.all_last:
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new
