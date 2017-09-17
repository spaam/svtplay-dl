from __future__ import absolute_import
import re
import copy
import os

from svtplay_dl.service import Service

from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils import filenamify
from svtplay_dl.utils.urllib import urljoin
from svtplay_dl.error import ServiceError

class Cmore(Service):
    supported_domains = ['www.cmore.se']

    def get(self):
        if not self.options.username or not self.options.password:
            yield ServiceError("You need username and password to download things from this site.")
            return
        token = self._login()
        if not token:
            yield ServiceError("Can't find authenticity_token needed to login")
            return
        res = self.http.get(self.url)
        match = re.search('data-asset-splash-section data-asset-id="([^"]+)"', res.text)
        if not match:
            yield ServiceError("Can't find video id")
            return
        url = "https://restapi.cmore.se/api/tve_web/asset/{0}/play.json?protocol=VUDASH".format(match.group(1))
        res = self.http.get(url, headers={"authorization": "Bearer {0}".format(token)})
        janson = res.json()

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "cmore"
            basename = self._autoname(match.group(1))
            if basename is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "%s-%s-%s" % (basename, match.group(1), self.options.service)
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
        url = "https://restapi.cmore.se/api/tve_web/asset/{0}.json?expand=metadata".format(vid)
        res = self.http.get(url)
        janson = res.json()["asset"]["metadata"]
        name = janson["title"]["$"]

        if "season" in janson:
            season = "{0:02d}".format(int(janson["season"]["$"]))
            name = "{0}.S{1}E{2:02d}".format(name, season, int(janson["episode"]["$"]))
        return name

    def find_all_episodes(self, options):
        episodes = []

        self._login()
        res = self.http.get(self.url)
        tags = re.findall('<a class="card__link" href="([^"]+)"', res.text)
        for i in tags:
            url = urljoin("https://www.cmore.se/", i)
            if url not in episodes:
                episodes.append(url)

        if options.all_last > 0:
            return sorted(episodes[-options.all_last:])
        return sorted(episodes)

    def _login(self):
        url = "https://www.cmore.se/login"
        res = self.http.get(url, cookies=self.cookies)
        match = re.search('authenticity_token" value="([^"]+)"', res.text)
        if not match:
            return None
        post = {"username": self.options.username, "password": self.options.password, "authenticity_token": match.group(1),
                "redirect": "true"}
        res = self.http.post("https://account.cmore.se/session?client=web", json=post, cookies=self.cookies)
        janson = res.json()
        token = janson["data"]["vimond_token"]
        return token