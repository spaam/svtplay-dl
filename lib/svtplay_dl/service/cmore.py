from __future__ import absolute_import, unicode_literals
import re
from urllib.parse import urljoin, urlparse
import logging

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Cmore(Service):
    supported_domains = ['www.cmore.se', 'www.cmore.dk', 'www.cmore.no', 'www.cmore.fi']

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

        metaurl = "https://playback-api.b17g.net/asset/{}?service=cmore.{}" \
                  "&device=browser&drm=widevine&protocol=dash%2Chls".format(self.output["id"], tld)
        res = self.http.get(metaurl)
        janson = res.json()
        self._autoname(janson)
        if janson["metadata"]["isDrmProtected"]:
            yield ServiceError("Can't play this because the video got drm.")
            return

        url = "https://playback-api.b17g.net/media/{}?service=cmore.{}&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"], tld)
        res = self.http.request("get", url, cookies=self.cookies, headers={"authorization": "Bearer {0}".format(token)})
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return

        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(self.config, self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                               res.json()["playbackItem"]["manifestUrl"], output=self.output)
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
            url = urljoin("https://www.cmore.{}/".format(self._gettld()), i)
            if url not in episodes:
                episodes.append(url)

        if config.get("all_last") > 0:
            return sorted(episodes[-config.get("all_last"):])
        return sorted(episodes)

    def _gettld(self):
        if isinstance(self.url, list):
            parse = urlparse(self.url[0])
        else:
            parse = urlparse(self.url)
        return re.search(r'\.(\w{2})$', parse.netloc).group(1)

    def _login(self):
        tld = self._gettld()
        url = "https://www.cmore.{}/login".format(tld)
        res = self.http.get(url, cookies=self.cookies)
        if self.config.get("cmoreoperator"):
            post = {"username": self.config.get("username"), "password": self.config.get("password"),
                    "operator": self.config.get("cmoreoperator"), "country_code": tld}
        else:
            post = {"username": self.config.get("username"), "password": self.config.get("password")}
        res = self.http.post("https://account.cmore.{}/session?client=cmore-web-prod".format(tld), json=post, cookies=self.cookies)
        if res.status_code >= 400:
            return None, "Wrong username or password"
        janson = res.json()
        token = janson["data"]["vimond_token"]
        return token, None

    def operatorlist(self):
        res = self.http.get("https://tve.cmore.se/country/{0}/operator?client=cmore-web".format(self._gettld()))
        for i in res.json()["data"]["operators"]:
            print("operator: '{0}'".format(i["name"].lower()))

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
