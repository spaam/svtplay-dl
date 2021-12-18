import logging
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Cmore(Service):
    supported_domains = ["www.cmore.se", "www.cmore.dk", "www.cmore.no", "www.cmore.fi"]

    def get(self):
        if not self.config.get("username") or not self.config.get("password"):
            yield ServiceError("You need username and password to download things from this site.")
            return

        token, message = self._login()
        if not token:
            yield ServiceError(message)
            return

        vid = self._get_vid()
        if not vid:
            yield ServiceError("Can't find video id")
            return

        tld = self._gettld()
        self.output["id"] = vid

        metaurl = f"https://playback-api.b17g.net/asset/{self.output['id']}?service=cmore.{tld}&device=browser&drm=widevine&protocol=dash%2Chls"
        res = self.http.get(metaurl)
        janson = res.json()
        self._autoname(janson)
        if janson["metadata"]["isDrmProtected"]:
            yield ServiceError("Can't play this because the video got drm.")
            return

        url = f"https://playback-api.b17g.net/media/{self.output['id']}?service=cmore.{tld}&device=browser&protocol=hls%2Cdash&drm=widevine"
        res = self.http.request("get", url, cookies=self.cookies, headers={"authorization": f"Bearer {token}"})
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return

        jansson = res.json()
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

    def find_all_episodes(self, config):
        episodes = []
        seasons = []

        token, message = self._login()
        if not token:
            logging.error(message)
            return episodes

        parse = urlparse(self.url)
        url = f"https://www.cmore.{self._gettld()}/page-data{parse.path}/page-data.json"
        res = self.http.get(url)
        if res.status_code > 400:
            logging.warning("Bad url? it only work with series")
            return episodes

        janson = res.json()

        if "mutualSeasonData" in janson["result"]["pageContext"]:
            path = janson["result"]["pageContext"]["mutualSeasonData"]["serieRelativeUrl"]
            seasons = janson["result"]["pageContext"]["mutualSeasonData"]["seasonNumbers"]
        elif "mutualEpisodeData" in janson["result"]["pageContext"]:
            path = janson["result"]["pageContext"]["mutualEpisodeData"]["serieRelativeUrl"]
            seasons = janson["result"]["pageContext"]["mutualEpisodeData"]["seasonNumbers"]
        elif "serie" in janson["result"]["pageContext"]:
            path = janson["result"]["pageContext"]["serie"]["relativeUrl"]
            seasons = janson["result"]["pageContext"]["serie"]["seasonNumbers"]
        else:
            logging.warning("Can't find info needed to find episodes")

        for season in seasons:
            url = f"https://www.cmore.se/page-data{path}/sasong-{season}/page-data.json"
            res = self.http.get(url)
            janson = res.json()
            for episode in janson["result"]["pageContext"]["season"]["selectedEpisodes"]:
                episode_url = f'https://www.cmore.{self._gettld()}{episode["relativeUrl"]}'
                if episode_url not in episodes:
                    episodes.append(episode_url)

        if config.get("all_last") > 0:
            return sorted(episodes[-config.get("all_last") :])
        return sorted(episodes)

    def _gettld(self):
        if isinstance(self.url, list):
            parse = urlparse(self.url[0])
        else:
            parse = urlparse(self.url)
        return re.search(r"\.(\w{2})$", parse.netloc).group(1)

    def _login(self):
        tld = self._gettld()
        if self.config.get("cmoreoperator"):
            url = (
                f"https://tve.cmore.se/country/{tld}/operator/{self.config.get('cmoreoperator')}"
                f"/user/{self.config.get('username')}/exists?client=cmore-web-prod"
            )
            post = {
                "password": self.config.get("password"),
            }
        else:
            url = "https://account-delta.b17g.services/api?client=cmore-web"
            post = {
                "query": "mutation($username: String, $password: String, $site: String) { login(credentials:"
                "{username: $username, password: $password}, site: $site) { user { ...UserFields } session { token vimondToken } }} "
                "fragment UserFields on User { acceptedCmoreTerms acceptedPlayTerms countryCode email firstName genericAds "
                "lastName tv4UserDataComplete userId username yearOfBirth zipCode type}",
                "variables": {"username": self.config.get("username"), "password": self.config.get("password"), "site": "CMORE_SE"},
            }

        res = self.http.post(url, json=post, cookies=self.cookies)
        if res.status_code >= 400:
            return None, "Wrong username or password"
        janson = res.json()
        token = janson["data"]["login"]["session"]["vimondToken"]
        return token, None

    def operatorlist(self):
        res = self.http.get(f"https://tve.cmore.se/country/{self._gettld()}/operator?client=cmore-web-prod")
        for i in res.json()["data"]["operators"]:
            print(f"operator: '{i['name'].lower()}")

    def _get_vid(self):
        res = self.http.get(self.url)
        match = re.search('data-asset-id="([^"]+)"', res.text)
        if match:
            return match.group(1)

        parse = urlparse(self.url)
        match = re.search(r"/(\d+)-[\w-]+$", parse.path)
        if match:
            return match.group(1)

        return None

    def _autoname(self, janson):
        if "seriesTitle" in janson["metadata"]:
            self.output["title"] = janson["metadata"]["seriesTitle"]
            self.output["episodename"] = janson["metadata"]["episodeTitle"]
        else:
            self.output["title"] = janson["metadata"]["title"]
        self.output["season"] = janson["metadata"]["seasonNumber"]
        self.output["episode"] = janson["metadata"]["episodeNumber"]
        self.config.set("live", janson["metadata"]["isLive"])
