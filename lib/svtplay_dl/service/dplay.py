# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os
import hashlib
import random

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.error import ServiceError
from svtplay_dl.utils import filenamify, is_py2
from svtplay_dl.log import log


class Dplay(Service):
    supported_domains = ['dplay.se', 'dplay.dk', "dplay.no"]

    def get(self):
        parse = urlparse(self.url)
        self.domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)

        if not self._token():
            log.error("Something went wrong getting token for requests")

        if self.options.username and self.options.password:
            premium = self._login()
            if not premium:
                log.warning("Wrong username/password.")

        channel = False
        if "kanaler" in parse.path:
            match = re.search("kanaler/([^/]+)$", parse.path)
            path = "/channels/{}".format(match.group(1))
            url = "https://disco-api.{}/content{}".format(self.domain, path)
            channel = True
            self.options.live = True
        elif "program" in parse.path:
            match = re.search("(programmer|program)/([^/]+)$", parse.path)
            path = "/shows/{}".format(match.group(2))
            url = "https://disco-api.{}/content{}".format(self.domain, path)
            res = self.http.get(url, headers={"x-disco-client": "WEB:UNKNOWN:dplay-client:0.0.1"})
            programid = res.json()["data"]["id"]
            qyerystring = "include=primaryChannel,show&filter[videoType]=EPISODE&filter[show.id]={}&" \
                          "page[size]=100&sort=seasonNumber,episodeNumber,-earliestPlayableStart".format(programid)
            res = self.http.get("https://disco-api.{}/content/videos?{}".format(self.domain, qyerystring))
            janson = res.json()
            vid = 0
            slug = None
            for i in janson["data"]:
                if int(i["id"]) > vid:
                    vid = int(i["id"])
                    slug = i["attributes"]["path"]
            if slug:
                url = "https://disco-api.{}/content/videos/{}".format(self.domain, slug)
            else:
                yield ServiceError("Cant find latest video on program url")
                return
        else:
            match = re.search("(videos|videoer)/(.*)$", parse.path)
            url = "https://disco-api.{}/content/videos/{}".format(self.domain, match.group(2))
        res = self.http.get(url, headers={"x-disco-client": "WEB:UNKNOWN:dplay-client:0.0.1"})
        janson = res.json()
        if "errors" in janson:
            yield ServiceError("Cant find any videos on this url")
            return

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "dplay"
            if channel:
                name = filenamify(janson["data"]["attributes"]["name"])
            else:
                name = self._autoname(janson)
            if name is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "{0}-{1}-{2}".format(name, janson["data"]["id"], self.options.service)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        api = "https://disco-api.{}/playback/videoPlaybackInfo/{}".format(self.domain, janson["data"]["id"])
        res = self.http.get(api)
        if res.status_code > 400:
            yield ServiceError("You dont have permission to watch this")
            return
        streams = hlsparse(self.options, self.http.request("get", res.json()["data"]["attributes"]["streaming"]["hls"]["url"]),
                           res.json()["data"]["attributes"]["streaming"]["hls"]["url"], httpobject=self.http)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]

    def _autoname(self, jsondata):
        match = re.search('^([^/]+)/', jsondata["data"]["attributes"]["path"])
        show = match.group(1)
        season = jsondata["data"]["attributes"]["seasonNumber"]
        episode = jsondata["data"]["attributes"]["episodeNumber"]
        name = jsondata["data"]["attributes"]["name"]
        if is_py2:
            show = filenamify(show).encode("latin1")
            name = filenamify(name).encode("latin1")
        else:
            show = filenamify(show)

        return filenamify("{0}.s{1:02d}e{2:02d}.{3}".format(show, int(season), int(episode), name))

    def find_all_episodes(self, options):
        parse = urlparse(self.url)
        self.domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)

        match = re.search("^/(program|programmer|videos|videoer)/([^/]+)", parse.path)
        if not match:
            log.error("Can't find show name")
            return None

        if not self._token():
            log.error("Something went wrong getting token for requests")

        premium = False
        if self.options.username and self.options.password:
            premium = self._login()
            if not premium:
                log.warning("Wrong username/password.")

        url = "https://disco-api.{}/content/shows/{}".format(self.domain, match.group(2))
        res = self.http.get(url)
        programid = res.json()["data"]["id"]
        seasons = res.json()["data"]["attributes"]["seasonNumbers"]
        episodes = []
        for season in seasons:
            qyerystring = "include=primaryChannel,show&filter[videoType]=EPISODE&filter[show.id]={}&filter[seasonNumber]={}&" \
                          "page[size]=100&sort=seasonNumber,episodeNumber,-earliestPlayableStart".format(programid, season)
            res = self.http.get("https://disco-api.{}/content/videos?{}".format(self.domain, qyerystring))
            janson = res.json()
            for i in janson["data"]:
                if not premium and not "Free" in i["attributes"]["packages"]:
                    continue
                episodes.append("https://www.{}/videos/{}".format(self.domain, i["attributes"]["path"]))
        if len(episodes) == 0:
            log.error("Cant find any playable files")
        if options.all_last > 0:
            return episodes[:options.all_last]
        return episodes

    def _login(self):
        url = "https://disco-api.{}/login".format(self.domain)
        login = {"credentials": {"username": self.options.username, "password": self.options.password}}
        res = self.http.post(url, json=login)
        if res.status_code > 400:
            return False
        return True

    def _token(self):
        # random device id for cookietoken
        deviceid = hashlib.sha256(bytes(int(random.random()*1000))).hexdigest()
        url = "https://disco-api.{}/token?realm={}&deviceId={}&shortlived=true".format(self.domain, self.domain.replace(".", ""), deviceid)
        res = self.http.get(url)
        if res.status_code > 400:
            return False
        return True
