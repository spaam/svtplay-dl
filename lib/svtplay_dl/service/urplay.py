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
        urldata = self.get_urldata()
        key = "currentProduct"
        match = re.search(r'/Player/Player" data-react-props="([^\"]+)\"', urldata)
        if not match:
            key = "program"
            match = re.search(r'/ProgramContainer" data-react-props="([^\"]+)\"', self.get_urldata())
            if not match:
                yield ServiceError("Can't find json info")
                return

        data = unescape(match.group(1))
        jsondata = json.loads(data)

        res = self.http.get("https://streaming-loadbalancer.ur.se/loadbalancer.json")
        loadbalancer = res.json()["redirect"]

        self.outputfilename(jsondata[key], urldata)

        for streaminfo in jsondata[key]["streamingInfo"].keys():
            stream = jsondata[key]["streamingInfo"][streaminfo]

            if streaminfo == "raw":
                if "sd" in stream:
                    url = "https://{}/{}playlist.m3u8".format(loadbalancer, stream["sd"]["location"])
                    streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output)
                    for n in list(streams.keys()):
                        yield streams[n]
                if "hd" in stream:
                    url = "https://{}/{}playlist.m3u8".format(loadbalancer, stream["hd"]["location"])
                    streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output)
                    for n in list(streams.keys()):
                        yield streams[n]
            if not (self.config.get("get_all_subtitles")) and (stream["default"]):
                yield subtitle(copy.copy(self.config), "wrst", stream["tt"]["location"].replace(".tt", ".vtt"), output=self.output)

            if self.config.get("get_all_subtitles") and "tt" in stream:
                label = stream["tt"]["language"]
                if stream["tt"]["scope"] != "complete":
                    label = "{}-{}".format(label, stream["tt"]["scope"])
                yield subtitle(copy.copy(self.config), "wrst", stream["tt"]["location"].replace(".tt", ".vtt"), label, output=copy.copy(self.output))

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

    def outputfilename(self, data, urldata):
        if "seriesTitle" in data:
            self.output["title"] = data["seriesTitle"]
            self.output["title_nice"] = data["seriesTitle"]
        if "episodeNumber" in data and data["episodeNumber"]:
            self.output["episode"] = str(data["episodeNumber"])
        if "title" in data:
            if self.output["title"] is None:
                self.output["title"] = data["title"]
            else:
                self.output["episodename"] = data["title"]
        if "id" in data and data["id"]:
            self.output["id"] = str(data["id"])

        # Try to match Season info from HTML (not available in json, it seems), e.g.: <button class="SeasonsDropdown-module__seasonButton___25Uyt" type="button"><span>Säsong 6</span>
        seasonmatch = re.search(r"class..SeasonsDropdown-module__seasonButton.*span.S.song (\d+)..span", urldata)
        if seasonmatch:
            self.output["season"] = seasonmatch.group(1)
        else:
            self.output["season"] = "1"  # No season info - probably show without seasons
