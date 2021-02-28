import logging
import re
from urllib.parse import urljoin
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
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

        metaurl = "https://playback-api.b17g.net/asset/{}?service=cmore.{}" "&device=browser&drm=widevine&protocol=dash%2Chls".format(
            self.output["id"],
            tld,
        )
        res = self.http.get(metaurl)
        janson = res.json()
        self._autoname(janson)
        if janson["metadata"]["isDrmProtected"]:
            yield ServiceError("Can't play this because the video got drm.")
            return

        url = "https://playback-api.b17g.net/media/{}?service=cmore.{}&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"], tld)
        res = self.http.request("get", url, cookies=self.cookies, headers={"authorization": f"Bearer {token}"})
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

    def find_all_episodes(self, config):
        episodes = []

        token, message = self._login()
        if not token:
            logging.error(message)
            return
        res = self.http.get(self.url)
        tags = re.findall('<a class="card__link" href="([^"]+)"', res.text)
        for i in tags:
            url = urljoin(f"https://www.cmore.{self._gettld()}/", i)
            if url not in episodes:
                episodes.append(url)

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
            url = "https://tve.cmore.se/country/{}/operator/{}/user/{}/exists?client=cmore-web-prod".format(
                tld,
                self.config.get("cmoreoperator"),
                self.config.get("username"),
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
            print("operator: '{}'".format(i["name"].lower()))

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
