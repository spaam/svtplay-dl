import json
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
    urlreg = r"/(movies|shows)/([^/]+)(/episode/([^/]+))?"
    urlreg2 = r"/(movies|shows)/([^/]+)"

    def get(self):
        self.data = self.get_urldata()
        parse = urlparse(self.url)

        match = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", self.data)
        if not match:
            yield ServiceError("Can't find video info")
            return
        janson_nn = json.loads(match.group(1))
        urlmatch = re.search(self.urlreg, parse.path)
        if not urlmatch:
            yield ServiceError("Can't find what video it is or live is not supported")
            return

        self._janson()
        episodeid = urlmatch.group(4)
        if episodeid is None:
            urlmatch = re.search(self.urlreg2, parse.path)
            if not urlmatch:
                yield ServiceError("Can't find what video it is or live is not supported")
                return
            episodeid = urlmatch.group(2)
        if "movieMetadata" in janson_nn["props"]["pageProps"] and janson_nn["props"]["pageProps"]["movieMetadata"]:
            self.output["title"] = janson_nn["props"]["pageProps"]["movieMetadata"]["title"]
        if "episodeMetadata" in janson_nn["props"]["pageProps"] and janson_nn["props"]["pageProps"]["episodeMetadata"]:
            title = janson_nn["props"]["pageProps"]["episodeMetadata"]["seriesTitle"]
            match = re.search(r", (s.son[g]*|kauise) [0-9]+$", title)
            if match:
                title = title.split(",")[0]
            self.output["title"] = title
            self.output["season"] = janson_nn["props"]["pageProps"]["episodeMetadata"]["seasonNum"]
            self.output["episode"] = janson_nn["props"]["pageProps"]["episodeMetadata"]["episodeNum"]
        self.output["id"] = episodeid[:8]
        url = f"https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/episode/{episodeid}/master.m3u8"
        sid = str(uuid.uuid1())
        params = {
            "advertisingId": "",
            "appName": "ios",
            "appVersion": self.appversion,
            "app_name": "ios",
            "clientDeviceType": "4",
            "clientID": self.playbackid,
            "clientModelNumber": "iPhone",
            "country": "SE",
            "deviceId": str(uuid.uuid1()),
            "deviceLat": "67.5056",
            "deviceLon": "20.1810",
            "deviceMake": "Apple",
            "deviceModel": "iPhone",
            "deviceType": "ios",
            "deviceVersion": "27_0",
            "marketingRegion": "SE",
            "serverSideAds": "false",
            "sessionID": sid,
            "sid": sid,
            "userId": "",
            "jwt": self.sessionToken,
            "includeExtendedEvents": "true",
        }
        res = self.http.request("get", url, params)
        playlists = hlsparse(
            self.config,
            res,
            res.request.url,
            self.output,
            filter=True,
            query_pass=True,
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
        if urlmatch.group(1) != "shows":
            logging.warning("Only works with tv shows")
            return episodes
        self.slug = urlmatch.group(2)
        self._janson()

        match = re.search(r"^/([^\/]+)/", parse.path)
        language = match.group(1)

        parse = urlparse(self.url)

        match = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", self.data)
        if not match:
            logging.error("Can't find video info")
            return episodes
        janson_nn = json.loads(match.group(1))

        hashid = None
        if "dehydratedState" not in janson_nn["props"]["pageProps"]:
            logging.error("Can't find any video info")
            return episodes
        for queries in janson_nn["props"]["pageProps"]["dehydratedState"]["queries"]:
            if "state" in queries and "data" in queries["state"] and "showHome" in queries["state"]["data"]:
                match = re.search(r"ptvm/series/([^\/]+)/featuredImage", queries["state"]["data"]["showHome"]["hero"]["standardImgForAllScreens"])
                if match:
                    hashid = match.group(1)

        rul = f"https://service-vod.clusters.pluto.tv/v4/vod/series/{hashid}/seasons?offset=0&page=0"

        res = self.http.request("get", rul, headers={"Authorization": f"Bearer {self.sessionToken}"})
        for season in res.json()["seasons"]:
            if "episodes" in season:
                for episode in season["episodes"]:
                    episodes.append(f"https://pluto.tv/{language}/shows/{self.slug}/episode/{episode['_id']}")

        return episodes

    def _janson(self) -> None:
        self.playbackid = str(uuid.uuid1())
        self.appversion = re.search('appVersion" content="([^"]+)"', self.data)
        self.query = {
            "query": "query PtvStart($params: StartParameters!) {\n  ptvStart(params: $params) {\n    deviceId\n    session {\n      id\n      jwt\n    }\n    refreshInSec\n  }\n}",
            "variables": {
                "params": {
                    "deviceModel": "web",
                    "drmCapabilities": "widevine:L3",
                    "isClientDNT": True,
                    "deviceId": self.playbackid,
                    "ptvAppName": "web",
                    "cmAudienceID": "",
                    "updateType": "v1v2",
                },
            },
            "operationName": "PtvStart",
        }
        res = self.http.request("post", "https://pluto.tv/api/tn/app-shell/graphql/", json=self.query)
        self.janson = res.json()
        self.sessionToken = self.janson["data"]["ptvStart"]["session"]["jwt"]
