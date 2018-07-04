# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals
import re
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4play.se']

    def get(self):
        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":
            end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = "https://bbr-l2v.akamaized.net/live/{0}/master.m3u8?in={1}&out={2}?".format(parse.path[9:],
                                                                                              start_time_stamp.isoformat(),
                                                                                              end_time_stamp.isoformat())

            self.config.set("live", True)
            streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output, hls_time_stamp=True)
            for n in list(streams.keys()):
                yield streams[n]
            return

        match = self._getjson()
        if not match:
            yield ServiceError("Can't find json data")
            return

        jansson = json.loads(match.group(1))
        vid = None
        for i in jansson:
            janson2 = json.loads(i["data"])
            json.dumps(janson2)
            if "videoAsset" in janson2["data"]:
                vid = janson2["data"]["videoAsset"]["id"]
                if janson2["data"]["videoAsset"]["is_drm_protected"]:
                    yield ServiceError("We can't download DRM protected content from this site.")
                    return
                if janson2["data"]["videoAsset"]["is_live"]:
                    self.config.set("live", True)
                if janson2["data"]["videoAsset"]["season"] > 0:
                    self.output["season"] = janson2["data"]["videoAsset"]["season"]
                if janson2["data"]["videoAsset"]["episode"] > 0:
                    self.output["episode"] = janson2["data"]["videoAsset"]["episode"]
                self.output["title"] = janson2["data"]["videoAsset"]["program"]["name"]
                self.output["episodename"] = janson2["data"]["videoAsset"]["title"]
                vid = str(vid)
                self.output["id"] = str(vid)
            if "program" in janson2["data"] and vid is None:
                if "contentfulPanels" in janson2["data"]["program"]:
                    match = re.search(r"[\/-](\d+)$", self.url)
                    if match and "panels" in janson2["data"]["program"]:
                        for n in janson2["data"]["program"]["panels"]:
                            for z in n["videoList"]["videoAssets"]:
                                if z["id"] == int(match.group(1)):
                                    vid = z["id"]
                                    self.output["id"] = str(vid)
                                    self.output["episodename"] = z["title"]
                                    self.output["title"] = z["program"]["name"]

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(vid)
        res = self.http.request("get", url, cookies=self.cookies)
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(self.config, self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                               res.json()["playbackItem"]["manifestUrl"], output=self.output, httpobject=self.http)
            for n in list(streams.keys()):
                yield streams[n]

    def _getjson(self):
        match = re.search(".prefetched = (\[.*\]);", self.get_urldata())
        return match

    def find_all_episodes(self, config):
        episodes = []
        items = []
        show = None
        match = self._getjson()
        jansson = json.loads(match.group(1))
        for i in jansson:
            janson2 = json.loads(i["data"])
            if "program" in janson2["data"]:
                if "panels" in janson2["data"]["program"]:
                    for n in janson2["data"]["program"]["panels"]:
                        if n["assetType"] == "EPISODE":
                            for z in n["videoList"]["videoAssets"]:
                                show = z["program_nid"]
                                items.append(z["id"])
                        if n["assetType"] == "CLIP" and config.get("include_clips"):
                            for z in n["videoList"]["videoAssets"]:
                                show = z["program_nid"]
                                items.append(z["id"])

        items = sorted(items)
        for item in items:
            episodes.append("https://www.tv4play.se/program/{}/{}".format(show, item))

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last"):]
        return episodes


class Tv4(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4.se']

    def get(self):
        match = re.search(r"[\/-](\d+)$", self.url)
        if not match:
            yield ServiceError("Cant find video id")
            return
        self.output["id"] = match.group(1)

        match = re.search("data-program-format='([^']+)'", self.get_urldata())
        if not match:
            yield ServiceError("Cant find program name")
            return
        self.output["title"] = match.group(1)

        match = re.search('img alt="([^"]+)" class="video-image responsive"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find title of the video")
            return
        self.output["episodename"] = match.group(1)

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"])
        res = self.http.request("get", url, cookies=self.cookies)
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(self.config, self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                               res.json()["playbackItem"]["manifestUrl"], output=self.output)
            for n in list(streams.keys()):
                yield streams[n]
