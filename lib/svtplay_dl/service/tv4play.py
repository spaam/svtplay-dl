# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
from datetime import datetime
from datetime import timedelta
from urllib.parse import quote
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.utils.http import download_thumbnails


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4play.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":
            end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = (
                f"https://bbr-l2v.akamaized.net/live/{parse.path[9:]}/master.m3u8?in={start_time_stamp.isoformat()}&out={end_time_stamp.isoformat()}?"
            )

            self.config.set("live", True)
            streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output, hls_time_stamp=True)
            for n in list(streams.keys()):
                yield streams[n]
            return

        token = self._login()
        if token is None:
            return ServiceError("You need username / password.")

        match = self._getjson(self.get_urldata())
        if not match:
            yield ServiceError("Can't find json data")
            return
        jansson = json.loads(match.group(1))

        if "params" not in jansson["query"]:
            yield ServiceError("Cant find video id for the video")
            return

        key_check = None
        for key in jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"].keys():
            if key.startswith("media"):
                key_check = key
        what = jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"][key_check]["__ref"]

        if what.startswith("Series:"):
            seriesid = jansson["props"]["apolloStateFromServer"][what]["id"]
            url = f"https://client-gateway.tv4.a2d.tv/graphql?operationName=suggestedEpisode&variables=%7B%22id%22%3A%22{seriesid}%22%7D&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%2232df600a3e3efb1362bae9ff73a5e7f929e75c154effb38d7b3516c3985e38e0%22%7D%7D"
            res = self.http.request("get", url, headers={"Client-Name": "tv4-web", "Client-Version": "4.0.0", "Content-Type": "application/json"})
            vid = res.json()["data"]["series"]["suggestedEpisode"]["episode"]["id"]
        else:
            vid = jansson["props"]["apolloStateFromServer"][what]["id"]

        url = f"https://playback2.a2d.tv/play/{vid}?service=tv4play&device=browser&protocol=hls%2Cdash&drm=widevine&browser=GoogleChrome&capabilities=live-drm-adstitch-2%2Cyospace3"
        res = self.http.request("get", url, headers={"Authorization": f"Bearer {token}"})
        jansson = res.json()

        item = jansson["metadata"]
        if item["isDrmProtected"]:
            yield ServiceError("We can't download DRM protected content from this site.")
            return

        if item["isLive"]:
            self.config.set("live", True)
        if item["seasonNumber"] > 0:
            self.output["season"] = item["seasonNumber"]
        if item["episodeNumber"] and item["episodeNumber"] > 0:
            self.output["episode"] = item["episodeNumber"]
        self.output["title"] = item["seriesTitle"]
        self.output["episodename"] = item["title"]
        self.output["id"] = str(vid)
        self.output["episodethumbnailurl"] = item["image"]

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

        if jansson["playbackItem"]["type"] == "hls":
            yield from hlsparse(
                self.config,
                self.http.request("get", jansson["playbackItem"]["manifestUrl"]),
                jansson["playbackItem"]["manifestUrl"],
                output=self.output,
                httpobject=self.http,
            )
            yield from dashparse(
                self.config,
                self.http.request("get", jansson["playbackItem"]["manifestUrl"].replace(".m3u8", ".mpd")),
                jansson["playbackItem"]["manifestUrl"].replace(".m3u8", ".mpd"),
                output=self.output,
                httpobject=self.http,
            )

    def _getjson(self, data):
        match = re.search(r"application\/json\">(.*\})<\/script>", data)
        return match

    def _login(self):
        if self.config.get("username") is None or self.config.get("password") is None:
            return None
        res = self.http.request(
            "post",
            "https://avod-auth-alb.a2d.tv/oauth/authorize",
            json={
                "client_id": "tv4-web",
                "response_type": "token",
                "credentials": {"username": self.config.get("username"), "password": self.config.get("password")},
            },
        )
        if res.status_code > 400:
            return None
        return res.json()["access_token"]

    def find_all_episodes(self, config):
        episodes = []
        items = []

        showid, jansson = self._get_seriesid(self.get_urldata(), dict())
        if showid is None:
            logging.error("Cant find any videos")
            return

        for season in jansson["props"]["apolloStateFromServer"][f"Series:{showid}"]["allSeasonLinks"]:
            graph_list = self._graphql(season["seasonId"])
            for i in graph_list:
                if i not in items:
                    items.append(i)

        if config.get("include_clips"):
            if jansson["props"]["apolloStateFromServer"][f"Series:{showid}"]["hasPanels"]:
                key_check = None
                for key in jansson["props"]["apolloStateFromServer"][f"Series:{showid}"].keys():
                    if key.startswith("panels("):
                        key_check = key

                if key_check:
                    for item in jansson["props"]["apolloStateFromServer"][f"Series:{showid}"][key_check]["items"]:
                        if item["__ref"].startswith("Clips"):
                            graph_list = self._graphclips(jansson["props"]["apolloStateFromServer"][item["__ref"]]["id"])
                            for clip in graph_list:
                                episodes.append(f"https://www.tv4play.se/klipp/{clip}")

        items = sorted(items)
        for item in items:
            episodes.append(f"https://www.tv4play.se/video/{item}")

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes

    def _get_seriesid(self, data, jansson):
        match = self._getjson(data)
        if not match:
            return None, jansson
        jansson = json.loads(match.group(1))
        if "params" not in jansson["query"]:
            return None, jansson
        showid = jansson["query"]["params"][0]
        key_check = None
        for key in jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"].keys():
            if key.startswith("media"):
                key_check = key
        what = jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"][key_check]["__ref"]
        if what.startswith("Episode"):
            series = jansson["props"]["apolloStateFromServer"][what]["series"]["__ref"].replace("Series:", "")
            res = self.http.request("get", f"https://www.tv4play.se/program/{series}/")
            showid, jansson = self._get_seriesid(res.text, jansson)
        return showid, jansson

    def _graphql(self, show):
        items = []
        nr = 0
        total = 100
        while nr <= total:
            variables = {"seasonId": show, "input": {"limit": 12, "offset": nr}}
            querystring = f"operationName=SeasonEpisodes&variables={quote(json.dumps(variables, separators=(',', ':')))}&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22ed1681cdf0f538949697babb57e34e399732046422df6ae60949c693362ca744%22%7D%7D"

            res = self.http.request(
                "get",
                f"https://client-gateway.tv4.a2d.tv/graphql?{querystring}",
                headers={"Client-Name": "tv4-web", "Client-Version": "4.0.0", "Content-Type": "application/json"},
            )
            janson = res.json()

            total = janson["data"]["season"]["episodes"]["pageInfo"]["totalCount"]
            for mediatype in janson["data"]["season"]["episodes"]["items"]:
                items.append(mediatype["id"])
            nr += 12
        return items

    def _graphclips(self, show):
        items = []
        nr = 0
        total = 100
        while nr <= total:
            variables = {"panelId": show, "offset": nr, "limit": 8}
            querystring = f"operationName=Panel&variables={quote(json.dumps(variables, separators=(',', ':')))}&extensions=%7B%22persistedQuery%22%3A%7B%22version%22%3A1%2C%22sha256Hash%22%3A%22843e9c11ac0512999fecd7646090d2e358c09ef30a4688d948d69dea17b82967%22%7D%7D"
            res = self.http.request(
                "get",
                f"https://client-gateway.tv4.a2d.tv/graphql?{querystring}",
                headers={"Client-Name": "tv4-web", "Client-Version": "4.0.0", "Content-Type": "application/json"},
            )
            janson = res.json()

            total = janson["data"]["panel"]["content"]["pageInfo"]["totalCount"]
            for mediatype in janson["data"]["panel"]["content"]["items"]:
                items.append(mediatype["clip"]["id"])
            nr += 12
        return items

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])


class Tv4(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4.se"]

    def get(self):
        match = re.search(r"application\/json\"\>(\{.*\})\<\/script", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video data'")
            return
        janson = json.loads(match.group(1))
        self.output["id"] = janson["query"]["id"]
        self.output["title"] = janson["query"]["slug"]
        if janson["query"]["type"] == "Article":
            vidasset = janson["props"]["pageProps"]["apolloState"][f"Article:{janson['query']['id']}"]["featured"]["__ref"]
            self.output["id"] = janson["props"]["pageProps"]["apolloState"][vidasset]["id"]
        url = f"https://playback2.a2d.tv/play/{self.output['id']}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine&capabilities=live-drm-adstitch-2%2Cexpired_assets"
        res = self.http.request("get", url, cookies=self.cookies)
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            yield from hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
