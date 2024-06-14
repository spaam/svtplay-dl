import datetime
import logging
import re
import uuid
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


class Plutotv(Service, OpenGraphThumbMixin):
    supported_domains = ["pluto.tv"]
    urlreg = r"/on-demand/(movies|series)/([^/]+)(/season/\d+/episode/([^/]+))?"
    urlreg2 = r"/on-demand/(movies|series)/([^/]+)(/episode/([^/]+))?"

    def get(self):
        self.data = self.get_urldata()
        parse = urlparse(self.url)

        urlmatch = re.search(self.urlreg, parse.path)
        if not urlmatch:
            yield ServiceError("Can't find what video it is or live is not supported")
            return

        self.slug = urlmatch.group(2)
        episodename = urlmatch.group(4)
        if episodename is None:
            urlmatch = re.search(self.urlreg2, parse.path)
            if not urlmatch:
                yield ServiceError("Can't find what video it is or live is not supported")
                return
            self.slug = urlmatch.group(2)
            episodename = urlmatch.group(4)
        self._janson()
        HLSplaylist = None

        for vod in self.janson["VOD"]:
            self.output["title"] = vod["name"]
            if "seasons" in vod:
                for season in vod["seasons"]:
                    if "episodes" in season:
                        for episode in season["episodes"]:
                            if episode["_id"] == episodename:
                                self.output["season"] = season["number"]
                                self.output["episodename"] = episode["name"]
                                for stich in episode["stitched"]["paths"]:
                                    if stich["type"] == "hls":
                                        HLSplaylist = f"{self.mediaserver}{stich['path']}?{self.stitcherParams}"
                                        if self.http.request("get", HLSplaylist).status_code < 400:
                                            break
            if "stitched" in vod and "paths" in vod["stitched"]:
                for stich in vod["stitched"]["paths"]:
                    if stich["type"] == "hls":
                        HLSplaylist = f"{self.mediaserver}{stich['path']}?{self.stitcherParams}"
                        if self.http.request("get", HLSplaylist).status_code < 400:
                            break

        if not HLSplaylist:
            yield ServiceError("Can't find video info")
            return

        playlists = hlsparse(
            self.config,
            self.http.request("get", HLSplaylist, headers={"Authorization": f"Bearer {self.sessionToken}"}),
            HLSplaylist,
            self.output,
            filter=True,
        )

        for playlist in playlists:
            if self.config.get("subtitle") and isinstance(playlist, subtitle):
                logging.warning("Subtitles are no longer supported for pluto.tv")
                continue
            yield playlist

    def find_all_episodes(self, options):
        episodes = []
        self.data = self.get_urldata()
        parse = urlparse(self.url)
        urlmatch = re.search(self.urlreg, parse.path)
        if urlmatch is None:
            logging.error("Can't find what video it is or live is not supported")
            return episodes
        if urlmatch.group(1) != "series":
            return episodes
        self.slug = urlmatch.group(2)
        self._janson()

        match = re.search(r"^/([^\/]+)/", parse.path)
        language = match.group(1)

        for vod in self.janson["VOD"]:
            if "seasons" in vod:
                for season in vod["seasons"]:
                    seasonnr = season["number"]
                    if "episodes" in season:
                        for episode in season["episodes"]:
                            episodes.append(f"https://pluto.tv/{language}/on-demand/series/{self.slug}/season/{seasonnr}/episode/{episode['_id']}")
        return episodes

    def _janson(self) -> None:
        self.appversion = re.search('appVersion" content="([^"]+)"', self.data)
        self.query = {
            "appName": "web",
            "appVersion": self.appversion.group(1) if self.appversion else "na",
            "deviceVersion": "119.0.0",
            "deviceModel": "web",
            "deviceMake": "firefox",
            "deviceType": "web",
            "clientID": uuid.uuid1(),
            "clientModelNumber": "1.0.0",
            "seriesIDs": self.slug,
            "serverSideAds": "false",
            "constraints": "",
            "drmCapabilities": "widevine%3AL3",
            "clientTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        res = self.http.request("get", "https://boot.pluto.tv/v4/start", params=self.query)
        self.janson = res.json()
        self.mediaserver = self.janson["servers"]["stitcher"]
        self.stitcherParams = self.janson["stitcherParams"]
        self.sessionToken = self.janson["sessionToken"]
