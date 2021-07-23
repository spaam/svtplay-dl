# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import datetime
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
REALMS = {"discoveryplus.se": "dplayse", "discoveryplus.no": "dplayno", "discoveryplus.dk": "dplaydk"}


class Discoveryplus(Service):
    supported_domains = ["discoveryplus.se", "discoveryplus.no", "discoveryplus.dk"]
    packages = []

    def get(self):
        parse = urlparse(self.url)
        self.domain = re.search(r"(discoveryplus\.\w\w)", parse.netloc).group(1)

        if not self._token():
            logging.error("Something went wrong getting token for requests")

        if not self._login():
            yield ServiceError("You need the 'st' cookie from your web brower for the site to make it work")
            return

        channel = False
        if "kanaler" in parse.path:
            match = re.search("kanaler/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Can't detect 'kanaler'")
                return
            path = f"/channels/{match.group(1)}"
            url = f"https://disco-api.{self.domain}/content{path}"
            channel = True
            self.config.set("live", True)
        elif "program" in parse.path:
            match = re.search("(programmer|program)/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Can't find program url")
                return
            path = f"/shows/{match.group(2)}"
            url = f"https://disco-api.{self.domain}/content{path}"
            res = self.http.get(url, headers={"x-disco-client": "WEB:UNKNOWN:dplay-client:0.0.1"})
            programid = res.json()["data"]["id"]
            qyerystring = (
                "include=primaryChannel,show&filter[videoType]=EPISODE&filter[show.id]={}&"
                "page[size]=100&sort=seasonNumber,episodeNumber,-earliestPlayableStart".format(programid)
            )
            res = self.http.get(f"https://disco-api.{self.domain}/content/videos?{qyerystring}")
            janson = res.json()
            vid = 0
            slug = None
            for i in janson["data"]:
                if int(i["id"]) > vid:
                    vid = int(i["id"])
                    slug = i["attributes"]["path"]
            if slug:
                url = f"https://disco-api.{self.domain}/content/videos/{slug}"
            else:
                yield ServiceError("Cant find latest video on program url")
                return
        else:
            match = re.search("(videos|videoer)/(.*)$", parse.path)
            if not match:
                match = re.search("olympics/([^/]+)/(.*)$", parse.path)
            url = f"https://disco-api.{self.domain}/content/videos/{match.group(2)}"
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
        for stream in streams:
            if isinstance(stream, subtitle):  # we get the subtitles from the hls playlist.
                if self.config.get("get_all_subtitles"):
                    yield stream
                else:
                    if stream.subfix in country and country[stream.subfix] in self.domain:
                        yield stream
            else:
                yield stream

    def _autoname(self, jsondata):
        if "seasonNumber" in jsondata["data"]["attributes"]:
            match = re.search("^([^/]+)/", jsondata["data"]["attributes"]["path"])
            self.output["title"] = match.group(1)
            self.output["season"] = int(jsondata["data"]["attributes"]["seasonNumber"])
            self.output["episode"] = int(jsondata["data"]["attributes"]["episodeNumber"])
            self.output["episodename"] = jsondata["data"]["attributes"]["name"]
        else:
            self.output["title"] = jsondata["data"]["attributes"]["name"]
            self.output["episodename"] = jsondata["data"]["attributes"]["secondaryTitle"]
        return self.output["title"]

    def find_all_episodes(self, config):
        parse = urlparse(self.url)
        self.domain = re.search(r"(discoveryplus\.\w\w)", parse.netloc).group(1)
        episodes = []

        route = None
        program_video = True
        match = re.search("^/((program|programmer|videos|videoer)/[^/]+)", parse.path)
        if not match:
            match = re.search("^/(olympics.*)", parse.path)
            if not match:
                logging.error("Can't find show name")
                return None
            program_video = False

        route = match.group(1)

        if not self._login():
            logging.error("Need the 'st' cookie to work")
            return None

        if not self._token():
            logging.error("Something went wrong getting token for requests")

        self._getpackages()

        if program_video:
            episodes = self._program_videos(route)
        else:
            episodes = self._sports(route)

        if not episodes:
            logging.error("Cant find any playable files")
        if config.get("all_last") > 0:
            return episodes[: config.get("all_last")]
        return episodes

    def _program_videos(self, route):
        seasons = []
        episodes = []
        showid = None

        url = f"http://disco-api.{self.domain}/cms/routes/{route}?decorators=viewingHistory&include=default"
        res = self.http.get(url)
        if res.status_code > 400:
            logging.error("Cant find any videos. wrong url?")
            return episodes

        for what in res.json()["included"]:
            if "attributes" in what and "component" in what["attributes"] and what["attributes"]["component"]["id"] == "tabbed-content":
                programid = what["id"]
                for ses in what["attributes"]["component"]["filters"]:
                    if ses["id"] == "seasonNumber":
                        for opt in ses["options"]:
                            if "value" not in opt:
                                continue
                            seasons.append(opt["value"])
                if "mandatoryParams" in what["attributes"]["component"]:
                    showid = what["attributes"]["component"]["mandatoryParams"]

        if programid:
            for season in seasons:
                page = 1
                totalpages = 1
                while page <= totalpages:
                    querystring = "decorators=viewingHistory&include=default&page[items.number]={}&pf[seasonNumber]={}".format(
                        page,
                        season,
                    )
                    if showid:
                        querystring += f"&{showid}"
                    res = self.http.get(f"https://disco-api.{self.domain}/cms/collections/{programid}?{querystring}")
                    janson = res.json()
                    if "meta" not in janson["data"]:
                        page += 1
                        continue
                    totalpages = janson["data"]["meta"]["itemsTotalPages"]
                    for i in janson["included"]:
                        if i["type"] != "video":
                            continue
                        if i["attributes"]["videoType"] == "EPISODE" or i["attributes"]["videoType"] == "STANDALONE":
                            if not self._playablefile(i["attributes"]["availabilityWindows"]):
                                continue
                            episodes.append("https://www.{}/videos/{}".format(self.domain, i["attributes"]["path"]))
                    page += 1
        return episodes

    def _sports(self, route):
        episodes = []
        page = 1
        totalpages = 1
        while page <= totalpages:
            querystring = f"decorators=viewingHistory&include=default&page[items.size]=100&page[items.number]={page}"
            url = f"http://disco-api.{self.domain}/cms/routes/{route}?{querystring}"
            res = self.http.get(url)
            if res.status_code > 400:
                logging.error("Cant find any videos. wrong url?")
                return episodes

            for i in res.json()["included"]:
                if i["type"] != "video":
                    continue
                if i["attributes"]["videoType"] == "STANDALONE":
                    if not self._playablefile(i["attributes"]["availabilityWindows"]):
                        continue
                    episodes.append("https://www.{}/videos/{}".format(self.domain, i["attributes"]["path"]))
            page += 1
        return episodes

    def _login(self):
        res = self.http.get(f"https://disco-api.{self.domain}/users/me", headers={"authority": f"disco-api.{self.domain}"})
        if res.status_code >= 400:
            return False
        if not res.json()["data"]["attributes"]["anonymous"]:
            return True
        return False

    def _token(self) -> bool:
        # random device id for cookietoken
        deviceid = hashlib.sha256(bytes(int(random.random() * 1000))).hexdigest()
        url = f"https://disco-api.{self.domain}/token?realm={REALMS[self.domain]}&deviceId={deviceid}&shortlived=true"
        res = self.http.get(url)
        if res.status_code >= 400:
            return False
        return True

    def _getpackages(self):
        res = self.http.get(f"https://disco-api.{self.domain}/users/me", headers={"authority": f"disco-api.{self.domain}"})
        if res.status_code < 400:
            self.packages.extend(res.json()["data"]["attributes"]["packages"])

    def _playablefile(self, needs):
        playable = False
        now = datetime.datetime.utcnow()
        for package in self.packages:
            for need in needs:
                if package != need["package"]:
                    continue
                start = datetime.datetime.strptime(need["playableStart"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
                if now > start:
                    if "playableEnd" in need:
                        end = datetime.datetime.strptime(need["playableEnd"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=None)
                        if now < end:
                            playable = True
                    else:
                        playable = True
        return playable
