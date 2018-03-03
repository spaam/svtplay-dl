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
            url = jsondata["streaming_config"]["loadbalancer"]
            if url[:1] == "/":
                url = "https:{}".format(url)
            lbjson = self.http.request("get", url).text
            lbjson = json.loads(lbjson)
            basedomain = lbjson["redirect"]
        http = "https://{0}/{1}".format(basedomain, jsondata["file_http"])
        hd = None
        if len(jsondata["file_http_hd"]) > 0:
            http_hd = "https://{0}/{1}".format(basedomain, jsondata["file_http_hd"])
            hls_hd = "{0}{1}".format(http_hd, jsondata["streaming_config"]["http_streaming"]["hls_file"])
            hd = True
        hls = "{0}{1}".format(http, jsondata["streaming_config"]["http_streaming"]["hls_file"])
        streams = hlsparse(self.options, self.http.request("get", hls), hls)
        for n in list(streams.keys()):
            yield streams[n]
        if hd:
            streams = hlsparse(self.options, self.http.request("get", hls_hd), hls_hd)
            for n in list(streams.keys()):
                yield streams[n]

    def find_all_episodes(self, options):
        parse = urlparse(self.url)
        episodes = []

        if parse.netloc == "urskola.se":
            data = self.get_urldata()
            match = re.search('data-limit="[^"]+" href="([^"]+)"', data)
            if match:
                res = self.http.get(urljoin("https://urskola.se", match.group(1)))
                data = res.text
            tags = re.findall('<a class="puff program tv video" title="[^"]+" href="([^"]+)"', data)
            for i in tags:
                url = urljoin("https://urskola.se/", i)
                if url not in episodes:
                    episodes.append(url)
        else:
            match = re.search("/program/\d+-(\w+)-", parse.path)
            if not match:
                log.error("Can't find any videos")
                return None
            keyword = match.group(1)
            all_links = re.findall('card-link" href="([^"]+)"', self.get_urldata())
            for i in all_links:
                match = re.search("/program/\d+-(\w+)-", i)
                if match and match.group(1) == keyword:
                    episodes.append(urljoin("https://urplay.se/", i))

        episodes_new = []
        n = 0
        for i in episodes:
            if n == options.all_last:
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new
