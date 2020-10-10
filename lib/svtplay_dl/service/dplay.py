# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import hashlib
import logging
import random
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


country = {"sv": ".se", "da": ".dk", "no": ".no"}


class Dplay(Service):
    supported_domains = ["dplay.se", "dplay.dk", "dplay.no"]

    def get(self):
        parse = urlparse(self.url)
        self.domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)

        if not self._token():
            logging.error("Something went wrong getting token for requests")

        if not self._login():
            yield ServiceError("Need the 'st' cookie to work")
            return

        channel = False
        if "kanaler" in parse.path:
            match = re.search("kanaler/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Can't detect 'kanaler'")
                return
            path = "/channels/{}".format(match.group(1))
            url = "https://disco-api.{}/content{}".format(self.domain, path)
            channel = True
            self.config.set("live", True)
        elif "program" in parse.path:
            match = re.search("(programmer|program)/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Can't find program url")
                return
            path = "/shows/{}".format(match.group(2))
            url = "https://disco-api.{}/content{}".format(self.domain, path)
            res = self.http.get(url, headers={"x-disco-client": "WEB:UNKNOWN:dplay-client:0.0.1"})
            programid = res.json()["data"]["id"]
            qyerystring = (
                "include=primaryChannel,show&filter[videoType]=EPISODE&filter[show.id]={}&"
                "page[size]=100&sort=seasonNumber,episodeNumber,-earliestPlayableStart".format(programid)
            )
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

        if channel:
            name = janson["data"]["attributes"]["name"]
            self.output["title"] = name
        else:
            name = self._autoname(janson)
        if name is None:
            yield ServiceError("Cant find vid id for autonaming")
            return
        self.output["id"] = janson["data"]["id"]

        api = "https://disco-api.{}/playback/videoPlaybackInfo/{}?usePreAuth=true".format(self.domain, janson["data"]["id"])
        res = self.http.get(api)
        if res.status_code > 400:
            yield ServiceError("You dont have permission to watch this")
            return
        streams = hlsparse(
            self.config,
            self.http.request("get", res.json()["data"]["attributes"]["streaming"]["hls"]["url"]),
            res.json()["data"]["attributes"]["streaming"]["hls"]["url"],
            httpobject=self.http,
            output=self.output,
        )
        for n in list(streams.keys()):
            if isinstance(streams[n], subtitle):  # we get the subtitles from the hls playlist.
                if self.config.get("get_all_subtitles"):
                    yield streams[n]
                else:
                    if streams[n].subfix in country and country[streams[n].subfix] in self.domain:
                        yield streams[n]
            else:
                yield streams[n]

    def _autoname(self, jsondata):
        match = re.search("^([^/]+)/", jsondata["data"]["attributes"]["path"])
        self.output["title"] = match.group(1)
        self.output["season"] = int(jsondata["data"]["attributes"]["seasonNumber"])
        self.output["episode"] = int(jsondata["data"]["attributes"]["episodeNumber"])
        self.output["episodename"] = jsondata["data"]["attributes"]["name"]
        return self.output["title"]

    def find_all_episodes(self, config):
        parse = urlparse(self.url)
        self.domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)
        programid = None
        seasons = []
        match = re.search("^/(program|programmer|videos|videoer)/([^/]+)", parse.path)
        if not match:
            logging.error("Can't find show name")
            return None

        if not self._login():
            logging.error("Need the 'st' cookie to work")
            return None

        if not self._token():
            logging.error("Something went wrong getting token for requests")

        premium = self._checkpremium()
        url = "http://disco-api.{}/cms/routes/program/{}?decorators=viewingHistory&include=default".format(self.domain, match.group(2))
        res = self.http.get(url)
        for what in res.json()["included"]:
            if "attributes" in what and "alias" in what["attributes"] and "season" in what["attributes"]["alias"]:
                programid = what["id"]
                for ses in what["attributes"]["component"]["filters"]:
                    if ses["id"] == "seasonNumber":
                        for opt in ses["options"]:
                            seasons.append(opt["value"])
        episodes = []

        if programid:
            for season in seasons:
                page = 1
                totalpages = 1
                while page <= totalpages:
                    qyerystring = "decorators=viewingHistory&include=default&page[items.number]={}&&pf[seasonNumber]={}".format(page, season)
                    res = self.http.get("https://disco-api.{}/cms/collections/{}?{}".format(self.domain, programid, qyerystring))
                    janson = res.json()
                    totalpages = janson["data"]["meta"]["itemsTotalPages"]
                    for i in janson["included"]:
                        if i["type"] != "video":
                            continue
                        if i["attributes"]["videoType"] == "EPISODE":
                            if not premium and "Free" not in i["attributes"]["packages"]:
                                continue
                            episodes.append("https://www.{}/videos/{}".format(self.domain, i["attributes"]["path"]))
                    page += 1
        if not episodes:
            logging.error("Cant find any playable files")
        if config.get("all_last") > 0:
            return episodes[: config.get("all_last")]
        return episodes

    def _login(self):
        res = self.http.get("https://disco-api.{}/users/me".format(self.domain), headers={"authority": "disco-api.{}".format(self.domain)})
        if not res.json()["data"]["attributes"]["anonymous"]:
            return True
        return False

    def _token(self) -> bool:
        # random device id for cookietoken
        deviceid = hashlib.sha256(bytes(int(random.random() * 1000))).hexdigest()
        url = "https://disco-api.{}/token?realm={}&deviceId={}&shortlived=true".format(self.domain, self.domain.replace(".", ""), deviceid)
        res = self.http.get(url)
        if res.status_code >= 400:
            return False
        return True

    def _checkpremium(self) -> bool:
        res = self.http.get("https://disco-api.{}/users/me".format(self.domain), headers={"authority": "disco-api.{}".format(self.domain)})
        if res.status_code < 400:
            if "premium" in res.json()["data"]["attributes"]["products"]:
                return True
        return False
