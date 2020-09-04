# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re
from datetime import datetime
from datetime import timedelta
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4play.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":
            end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = "https://bbr-l2v.akamaized.net/live/{}/master.m3u8?in={}&out={}?".format(
                parse.path[9:], start_time_stamp.isoformat(), end_time_stamp.isoformat()
            )

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
        if "assetId" not in jansson["props"]["pageProps"]:
            yield ServiceError("Cant find video id for the video")
            return

        vid = jansson["props"]["pageProps"]["assetId"]
        janson2 = jansson["props"]["pageProps"]["initialApolloState"]
        item = janson2["VideoAsset:{}".format(vid)]

        if item["is_drm_protected"]:
            yield ServiceError("We can't download DRM protected content from this site.")
            return

        if item["live"]:
            self.config.set("live", True)
        if item["season"] > 0:
            self.output["season"] = item["season"]
        if item["episode"] > 0:
            self.output["episode"] = item["episode"]
        self.output["title"] = item["program_nid"]
        self.output["episodename"] = item["title"]
        self.output["id"] = str(vid)

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(vid)
        res = self.http.request("get", url, cookies=self.cookies)
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked or not available.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
                httpobject=self.http,
            )
            for n in list(streams.keys()):
                yield streams[n]

    def _getjson(self):
        match = re.search(r"application\/json\">(.*\})<\/script><script", self.get_urldata())
        return match

    def find_all_episodes(self, config):
        episodes = []
        items = []
        show = None
        match = self._getjson()
        jansson = json.loads(match.group(1))
        janson2 = jansson["props"]["pageProps"]["initialApolloState"]
        for i in janson2:
            if "VideoAsset:" in i:
                if janson2[i]["clip"] and config.get("include_clips"):
                    show = janson2[i]["program_nid"]
                    items.append(janson2[i]["id"])
                elif janson2[i]["clip"] is False:
                    show = janson2[i]["program_nid"]
                    items.append(janson2[i]["id"])

        items = sorted(items)
        for item in items:
            episodes.append("https://www.tv4play.se/program/{}/{}".format(show, item))

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes


class Tv4(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4.se"]

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
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
            for n in list(streams.keys()):
                yield streams[n]
