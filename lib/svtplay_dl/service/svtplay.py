# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import

import copy
import hashlib
import json
import logging
import re
from operator import itemgetter
from urllib.parse import parse_qs
from urllib.parse import urljoin
from urllib.parse import urlparse

import dateutil.parser
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import MetadataThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.text import filenamify

URL_VIDEO_API = "https://api.svt.se/video/"


class Svtplay(Service, MetadataThumbMixin):
    supported_domains = ["svtplay.se", "svt.se", "beta.svtplay.se", "svtflow.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.netloc == "www.svtplay.se" or parse.netloc == "svtplay.se":
            if parse.path[:6] != "/video" and parse.path[:6] != "/klipp" and parse.path[:8] != "/kanaler":
                yield ServiceError("This mode is not supported anymore. Need the url with the video.")
                return

        query = parse_qs(parse.query)
        self.access = None
        if "accessService" in query:
            self.access = query["accessService"]

        urldata = self.get_urldata()

        if parse.path[:8] == "/kanaler":
            match = re.search('data-video-id="([\\w-]+)"', urldata)

            if not match:
                yield ServiceError("Can't find video info.")
                return

            _url = urljoin(URL_VIDEO_API, match.group(1))
            res = self.http.get(_url)
            try:
                janson = res.json()
            except json.decoder.JSONDecodeError:
                yield ServiceError("Can't decode api request: {}".format(res.request.url))
                return
            videos = self._get_video(janson)
            self.config.set("live", True)
            yield from videos
            return

        match = re.search(r"__svtplay_apollo'] = ({.*});", urldata)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))
        self.visibleid = self._get_visibleid(janson)
        if not self.visibleid:
            yield ServiceError("Can't find video id")
            return

        vid = janson[self.visibleid]["videoSvtId"]

        self.outputfilename(janson)
        self.extrametadata(janson, self.visibleid)

        res = self.http.get(URL_VIDEO_API + vid)
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {}".format(res.request.url))
            return
        videos = self._get_video(janson)
        yield from videos

    def _get_video(self, janson):
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if i["format"] == "websrt" and "url" in i:
                    yield subtitle(copy.copy(self.config), "wrst", i["url"], output=self.output)

        if "videoReferences" in janson:
            if len(janson["videoReferences"]) == 0:
                yield ServiceError("Media doesn't have any associated videos.")
                return

            for i in janson["videoReferences"]:
                streams = None
                alt_streams = None
                alt = None
                query = parse_qs(urlparse(i["url"]).query)
                if "alt" in query and len(query["alt"]) > 0:
                    alt = self.http.get(query["alt"][0])

                if i["format"] == "hls":
                    streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    if alt:
                        alt_streams = hlsparse(self.config, self.http.request("get", alt.request.url), alt.request.url, output=self.output)
                elif i["format"] == "dash264" or i["format"] == "dashhbbtv":
                    streams = dashparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    if alt:
                        alt_streams = dashparse(self.config, self.http.request("get", alt.request.url), alt.request.url, output=self.output)

                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
                if alt_streams:
                    for n in list(alt_streams.keys()):
                        yield alt_streams[n]

    def _get_visibleid(self, janson):
        esceni = None
        for key in janson["ROOT_QUERY"].keys():
            if "listablesBy" in key:
                esceni = key
                break

        if esceni:
            return janson["ROOT_QUERY"][esceni][0]["id"]
        else:
            return esceni

    def _last_chance(self, videos, page, maxpage=2):
        if page > maxpage:
            return videos

        res = self.http.get("http://www.svtplay.se/sista-chansen?sida={}".format(page))
        match = re.search("__svtplay'] = ({.*});", res.text)
        if not match:
            return videos

        dataj = json.loads(match.group(1))
        pages = dataj["gridPage"]["pagination"]["totalPages"]

        for i in dataj["gridPage"]["content"]:
            videos.append(i["contentUrl"])
        page += 1
        videos.extend(self._last_chance(videos, page, pages))
        return videos

    def _genre(self, jansson):
        videos = []
        parse = urlparse(self._url)
        dataj = jansson["clusterPage"]
        tab = re.search("tab=(.+)", parse.query)
        if tab:
            tab = tab.group(1)
            for i in dataj["tabs"]:
                if i["slug"] == tab:
                    videos = self.videos_to_list(i["content"], videos)
        else:
            videos = self.videos_to_list(dataj["clips"], videos)

        return videos

    def find_all_episodes(self, config):
        parse = urlparse(self._url)

        videos = []
        tab = None
        if parse.query:
            query = parse_qs(parse.query)
            if "tab" in query:
                tab = query["tab"][0]

        if re.search("sista-chansen", parse.path):
            videos = self._last_chance(videos, 1)
        else:
            match = re.search(r"__svtplay_apollo'] = ({.*});", self.get_urldata())
            if not match:
                logging.error("Can't find video info.")
                return

            janson = json.loads(match.group(1))
            self.visibleid = self._get_visibleid(janson)
            if not self.visibleid:
                logging.error("Can't find video i")
                return

            match = re.search(r"__svtplay_apollo'] = ({.*});", self.get_urldata())
            if not match:
                logging.error("Can't find video info.")
                return videos
            janson = json.loads(match.group(1))
            episode = janson[self.visibleid]
            associatedContent = episode['associatedContent({"include":["season","productionPeriod","clips","upcoming"]})']

            keys = []
            videos = []
            if "urls" in episode:
                videos.append(janson[episode["urls"]["id"]]["svtplay"])
            for i in associatedContent:
                if tab:
                    section = "Selection:{}".format(tab)
                    if section == i["id"]:
                        keys.append(section)
                else:
                    if i["id"] == "Selection:upcoming":
                        continue
                    elif self.config.get("include_clips") and "Selection:clips" in i["id"]:
                        keys.append(i["id"])
                    elif "Selection:clips" not in i["id"]:
                        keys.append(i["id"])

            for i in keys:
                for n in janson[i]["items"]:
                    epi = janson[janson[n["id"]]["item"]["id"]]
                    if "variants" in epi:
                        for z in epi["variants"]:
                            if janson[janson[z["id"]]["urls"]["id"]]["svtplay"] not in videos:
                                videos.append(janson[janson[z["id"]]["urls"]["id"]]["svtplay"])
                    if janson[epi["urls"]["id"]]["svtplay"] not in videos:
                        videos.append(janson[epi["urls"]["id"]]["svtplay"])

        episodes = [urljoin("http://www.svtplay.se", x) for x in videos]

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes

    def videos_to_list(self, lvideos, videos):
        if "episodeNumber" in lvideos[0] and lvideos[0]["episodeNumber"]:
            lvideos = sorted(lvideos, key=itemgetter("episodeNumber"))
        for n in lvideos:
            parse = urlparse(n["contentUrl"])
            if parse.path not in videos:
                videos.append(parse.path)
            if "versions" in n:
                for i in n["versions"]:
                    parse = urlparse(i["contentUrl"])
                    if parse.path not in videos:
                        videos.append(parse.path)

        return videos

    def outputfilename(self, data):
        name = None
        desc = None
        pid = data[self.visibleid]["parent"]["id"]

        name = data[pid]["slug"]
        other = data[self.visibleid]["slug"]
        vid = data[self.visibleid]["id"]
        id = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        elif name is None:
            name = other
            other = None

        season, episode = self.seasoninfo(data)
        if "accessibility" in data[self.visibleid]:
            if data[self.visibleid]["accessibility"] == "AudioDescribed":
                desc = "syntolkat"
            if data[self.visibleid]["accessibility"] == "SignInterpreted":
                desc = "teckentolkat"

        if not other:
            other = desc
        elif desc:
            other += "-{}".format(desc)

        self.output["title"] = filenamify(name)
        self.output["id"] = id
        self.output["season"] = season
        self.output["episode"] = episode
        self.output["episodename"] = other

    def seasoninfo(self, data):
        season, episode = None, None

        if "episode" not in data[self.visibleid]:
            return season, episode

        episodeid = data[self.visibleid]["episode"]["id"]
        if "positionInSeason" not in data[episodeid]:
            return season, episode

        match = re.search(r"Säsong (\d+) — Avsnitt (\d+)", data[episodeid]["positionInSeason"])
        if not match:
            return season, episode

        season = "{:02d}".format(int(match.group(1)))
        episode = "{:02d}".format(int(match.group(2)))

        return season, episode

    def extrametadata(self, data, visibleid):
        episode = data[visibleid]

        self.output["tvshow"] = self.output["season"] is not None and self.output["episode"] is not None
        if "validFrom" in episode:
            self.output["publishing_datetime"] = int(dateutil.parser.parse(episode["validFrom"]).strftime("%s"))

        self.output["title_nice"] = data[data[visibleid]["parent"]["id"]]["name"]

        try:
            t = data[data[episode["parent"]["id"]]["image"]["id"]]
        except KeyError:
            t = ""
        if isinstance(t, dict):
            url = "https://www.svtstatic.se/image/original/default/{id}/{changed}?format=auto&quality=100".format(**t)
            self.output["showthumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["showthumbnailurl"] = url
        try:
            t = data[episode["image"]["id"]]
        except KeyError:
            t = ""
        if isinstance(t, dict):
            url = "https://www.svtstatic.se/image/original/default/{id}/{changed}?format=auto&quality=100".format(**t)
            self.output["episodethumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["episodethumbnailurl"] = url

        if "longDescription" in data[episode["parent"]["id"]]:
            self.output["showdescription"] = data[episode["parent"]["id"]]["longDescription"]

        if "longDescription" in episode:
            self.output["episodedescription"] = episode["longDescription"]
