from __future__ import absolute_import
from __future__ import unicode_literals
import re
import copy
import os

from svtplay_dl.service import Service
from svtplay_dl.log import log
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils import filenamify
from svtplay_dl.utils.urllib import urljoin, urlparse
from svtplay_dl.error import ServiceError


class Cmore(Service):
    supported_domains = ['www.cmore.se', 'www.cmore.dk', 'www.cmore.no', 'www.cmore.fi']

    def get(self):
        if not self.options.username or not self.options.password:
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

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "cmore"
            basename = self._autoname(match.group(1))
            if basename is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "{0}-{1}-{2}".format(basename, match.group(1), self.options.service)
            title = filenamify(title)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        if "drmProtected" in janson["playback"]:
            if janson["playback"]["drmProtected"]:
                yield ServiceError("DRM protected. Can't do anything")
                return

        if isinstance(janson["playback"]["items"]["item"], list):
            for i in janson["playback"]["items"]["item"]:
                if i["mediaFormat"] == "ism":
                    streams = dashparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                if i["mediaFormat"] == "webvtt":
                    yield subtitle(copy.copy(self.options), "wrst", i["url"])
        else:
            i = janson["playback"]["items"]["item"]
            if i["mediaFormat"] == "ism":
                streams = dashparse(self.options, self.http.request("get", i["url"]), i["url"])
                if streams:
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
            season = "{0:02d}".format(int(janson["season"]["$"]))
            name = "{0}.S{1}E{2:02d}".format(name, season, int(janson["episode"]["$"]))
        return name

    def find_all_episodes(self, options):
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

        if options.all_last > 0:
            return sorted(episodes[-options.all_last:])
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
        if self.options.cmoreoperator:
            post = {"username": self.options.username, "password": self.options.password,
                    "operator": self.options.cmoreoperator, "country_code": tld}
        else:
            post = {"username": self.options.username, "password": self.options.password}
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
