import datetime
import re
import uuid
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Plutotv(Service, OpenGraphThumbMixin):
    supported_domains = ["pluto.tv"]
    urlreg = r"/on-demand/(movies|series)/([^/]+)(/season/\d+/episode/([^/]+))?"

    def get(self):
        self.data = self.get_urldata()
        parse = urlparse(self.url)

        urlmatch = re.search(self.urlreg, parse.path)
        if not urlmatch:
            yield ServiceError("Can't find what video it is or live is not supported")
            return

        self.slug = urlmatch.group(2)
        episodename = urlmatch.group(4)
        self._janson()
        HLSplaylist = None
        found = False

        servicevod = f"https://service-vod.clusters.pluto.tv/v4/vod/slugs/{self.slug}"
        res = self.http.request("get", servicevod, params=self.query, headers={"Authorization": f"Bearer {self.sessionToken}"})
        janson2 = res.json()
        if janson2["type"] == "series":
            self.output["title"] = janson2["name"]
            for season in janson2["seasons"]:
                for episode in season["episodes"]:
                    if episode["slug"] == episodename and not found:
                        self.output["season"] = episode["season"]
                        self.output["episode"] = episode["number"]
                        for stich in episode["stitched"]["paths"]:
                            if stich["type"] == "hls":
                                HLSplaylist = f"{self.mediaserver}{stich['path']}?{self.stitcherParams}"
                                if self.http.request("get", HLSplaylist, headers={"Authorization": f"Bearer {self.sessionToken}"}).status_code < 400:
                                    found = True
        else:
            self.output["title"] == janson2["name"]
            for stich in janson2["stitched"]["paths"]:
                if stich["type"] == "hls":
                    HLSplaylist = f"{self.mediaserver}{stich['path']}?{self.stitcherParams}"

        if not HLSplaylist:
            yield ServiceError("Can't find video info")
            return

        yield from hlsparse(
            self.config,
            self.http.request("get", HLSplaylist, headers={"Authorization": f"Bearer {self.sessionToken}"}),
            HLSplaylist,
            self.output,
            filter=True,
        )

    def find_all_episodes(self, options):
        episodes = []
        self.data = self.get_urldata()
        parse = urlparse(self.url)
        urlmatch = re.search(self.urlreg, parse.path)
        if urlmatch.group(1) != "series":
            return episodes
        self.slug = urlmatch.group(2)
        self._janson()

        match = re.search(r"^/([^\/]+)/", parse.path)
        language = match.group(1)

        servicevod = f"https://service-vod.clusters.pluto.tv/v4/vod/slugs/{self.slug}"
        res = self.http.request("get", servicevod, params=self.query, headers={"Authorization": f"Bearer {self.sessionToken}"})
        janson2 = res.json()
        for season in janson2["seasons"]:
            seasonnr = season["number"]
            for episode in season["episodes"]:
                episodes.append(f"https://pluto.tv/{language}/on-demand/series/{self.slug}/season/{seasonnr}/episode/{episode['slug']}")
        return episodes

    def _janson(self) -> None:
        self.appversion = re.search('appVersion" content="([^"]+)"', self.data)
        self.query = {
            "appName": "web",
            "appVersion": self.appversion.group(1) if self.appversion else "na",
            "deviceVersion": "100.0.0",
            "deviceModel": "web",
            "deviceMake": "firefox",
            "deviceType": "web",
            "clientID": uuid.uuid1(),
            "clientModelNumber": "1.0.0",
            "episodeSlugs": self.slug,
            "serverSideAds": "false",
            "constraints": "",
            "drmCapabilities": "widevine%3AL3",
            "clientTime": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        res = self.http.request("get", "https://boot.pluto.tv/v4/start", params=self.query)
        janson = res.json()
        self.mediaserver = janson["servers"]["stitcher"]
        self.stitcherParams = janson["stitcherParams"]
        self.sessionToken = janson["sessionToken"]
