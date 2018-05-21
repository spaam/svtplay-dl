from __future__ import absolute_import, unicode_literals
import re
import copy
from urllib.parse import urljoin, urlparse

from svtplay_dl.service import Service
from svtplay_dl.log import log
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.subtitle import subtitle
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

        res = self.http.get(self.url)
        match = re.search('data-asset-id="([^"]+)"', res.text)
        if not match:
            yield ServiceError("Can't find video id")
            return

        tld = self._gettld()
        url = "https://restapi.cmore.{0}/api/tve_web/asset/{1}/play.json?protocol=VUDASH".format(tld, match.group(1))
        res = self.http.get(url, headers={"authorization": "Bearer {0}".format(token)})
        janson = res.json()
        if "error" in janson:
            yield ServiceError("This video is geoblocked")
            return

        basename = self._autoname(match.group(1))
        self.output["id"] = match.group(1)
        if basename is None:
            yield ServiceError("Cant find vid id for autonaming")
            return

        if "drmProtected" in janson["playback"]:
            if janson["playback"]["drmProtected"]:
                yield ServiceError("DRM protected. Can't do anything")
                return

        if isinstance(janson["playback"]["items"]["item"], list):
            for i in janson["playback"]["items"]["item"]:
                if i["mediaFormat"] == "ism":
                    streams = dashparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                if i["mediaFormat"] == "webvtt":
                    yield subtitle(copy.copy(self.config), "wrst", i["url"])
        else:
            i = janson["playback"]["items"]["item"]
            if i["mediaFormat"] == "ism":
                streams = dashparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]

    def _autoname(self, vid):
        url = "https://restapi.cmore.{0}/api/tve_web/asset/{1}.json?expand=metadata".format(self._gettld(), vid)
        res = self.http.get(url)
        janson = res.json()["asset"]["metadata"]
        if isinstance(janson["title"], list):
            for i in janson["title"]:
                if self._gettld() == "se":
                    if i["@xml:lang"] == "sv_SE":
                        name = i["$"]
                elif self._gettld() == "dk":
                    if i["@xml:lang"] == "da_DK":
                        name = i["$"]
                elif self._gettld() == "no":
                    if i["@xml:lang"] == "nb_NO":
                        name = i["$"]
                elif self._gettld() == "fi":
                    if i["@xml:lang"] == "fi_FI":
                        name = i["$"]
        else:
            name = janson["title"]["$"]

        if "season" in janson:
            self.output["season"] = int(janson["season"]["$"])
            self.output["episode"] = int(janson["episode"]["$"])
        self.output["title"] = name
        return self.output["title"]

    def find_all_episodes(self, config):
        episodes = []

        token, message = self._login()
        if not token:
            log.error(message)
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
        return re.search('\.(\w{2})$', parse.netloc).group(1)

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
