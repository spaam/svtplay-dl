# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import logging
import re
from html import unescape

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ["urplay.se", "ur.se", "betaplay.ur.se", "urskola.se"]

    def get(self):
        match = re.search(r'/Player/Player" data-react-props="([^\"]+)\"', self.get_urldata())
        if not match:
            yield ServiceError("Can't find json info")
            return

        data = unescape(match.group(1))
        jsondata = json.loads(data)

        res = self.http.get("https://streaming-loadbalancer.ur.se/loadbalancer.json")
        loadbalancer = res.json()["redirect"]

        for streaminfo in jsondata["currentProduct"]["streamingInfo"].keys():
            stream = jsondata["currentProduct"]["streamingInfo"][streaminfo]
            if stream["default"]:
                url = "https://{}/{}playlist.m3u8".format(loadbalancer, stream["sd"]["location"])
                streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]
                url = "https://{}/{}playlist.m3u8".format(loadbalancer, stream["hd"]["location"])
                streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]
                if not self.config.get("get_all_subtitles"):
                    yield subtitle(copy.copy(self.config), "tt", stream["tt"]["location"], output=self.output)

            if self.config.get("get_all_subtitles") and "tt" in stream:
                label = stream["tt"]["language"]
                if stream["tt"]["scope"] != "complete":
                    label = "{}-{}".format(label, stream["tt"]["scope"])
                yield subtitle(copy.copy(self.config), "tt", stream["tt"]["location"], label, output=self.output)

    def find_all_episodes(self, config):
        episodes = []

        match = re.search(r'/Player/Player" data-react-props="([^\"]+)\"', self.get_urldata())
        if not match:
            logging.error("Can't find json info")
            return

        data = unescape(match.group(1))
        jsondata = json.loads(data)

        for episode in jsondata["accessibleEpisodes"]:
            episodes.append("https://urplay.se/program/{}".format(episode["slug"]))
        episodes_new = []
        n = 0
        for i in episodes:
            if n == config.get("all_last"):
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new
