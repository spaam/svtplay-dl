# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import datetime
import hashlib
import json
import logging
import re
import time
from operator import itemgetter
from urllib.parse import parse_qs
from urllib.parse import urljoin
from urllib.parse import urlparse

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
    info_search_expr = r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>"

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
            ch = "ch-{}".format(parse.path[parse.path.rfind("/") + 1 :])
            _url = urljoin(URL_VIDEO_API, ch)
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

        match = re.search(self.info_search_expr, urldata)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))
        video_data = None
        vid = None
        for data_entry in janson["props"]["urqlState"].values():
            entry = json.loads(data_entry["data"])
            for key, data in entry.items():
                if key == "listablesByEscenicId" and "videoSvtId" in data[0]:
                    video_data = data[0]
                    vid = video_data["videoSvtId"]
                    break
            # if video_data:
            #    break

        if not vid and not self.visibleid:
            yield ServiceError("Can't find video id")
            return

        self.outputfilename(video_data)
        self.extrametadata(video_data)

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
                if i["format"] == "webvtt" and "url" in i:
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

                if i["format"][:3] == "hls":
                    streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    if alt:
                        alt_streams = hlsparse(self.config, self.http.request("get", alt.request.url), alt.request.url, output=self.output)
                elif i["format"][:4] == "dash":
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
        for data_entry in janson["props"]["urqlState"].values():
            entry = json.loads(data_entry["data"])
            for key in entry.keys():
                if "listablesBy" in key:
                    esceni = entry[key]
                    break
            if esceni:
                break

        if esceni:
            try:
                return esceni[0]["id"]
            except IndexError:
                return None
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
            match = re.search(self.info_search_expr, self.get_urldata())
            if not match:
                logging.error("Can't find video info.")
                return

            janson = json.loads(match.group(1))
            self.visibleid = self._get_visibleid(janson)
            if not self.visibleid:
                logging.error("Can't find video id. removed?")
                return

            match = re.search(self.info_search_expr, self.get_urldata())
            if not match:
                logging.error("Can't find video info.")
                return videos
            janson = json.loads(match.group(1))
            associatedContent = None

            for json_entry in janson["props"]["urqlState"].values():
                entry = json.loads(json_entry["data"])
                for key, data in entry.items():
                    if "listablesBy" in key and data[0]["associatedContent"][0]["id"] != "related":
                        associatedContent = data[0]["associatedContent"]
                        break
                if associatedContent:
                    break

            collections = []
            videos = []
            for i in associatedContent:
                if tab:
                    if tab == i["id"]:
                        collections.append(i)
                else:
                    if i["id"] == "upcoming":
                        continue
                    elif self.config.get("include_clips") and "clips" in i["id"]:
                        collections.append(i)
                    elif "clips" not in i["id"]:
                        collections.append(i)

            if not collections:
                logging.error("Can't find other episodes.")

            for i in collections:
                for epi in i["items"]:
                    if "variants" in epi["item"]:
                        for variant in epi["item"]["variants"]:
                            if variant["urls"]["svtplay"] not in videos:
                                videos.append(variant["urls"]["svtplay"])
                    if epi["item"]["urls"]["svtplay"] not in videos:
                        videos.append(epi["item"]["urls"]["svtplay"])

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

        name = data["parent"]["slug"]
        other = data["slug"]
        vid = data["id"]
        id = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        elif name is None:
            name = other
            other = None

        season, episode = self.seasoninfo(data)
        if "accessibility" in data:
            if data["accessibility"] == "AudioDescribed":
                desc = "syntolkat"
            if data["accessibility"] == "SignInterpreted":
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

        if "episode" not in data:
            return season, episode

        if "positionInSeason" not in data["episode"]:
            return season, episode

        match = re.search(r"Säsong (\d+) — Avsnitt (\d+)", data["episode"]["positionInSeason"])
        if not match:
            return season, episode

        season = "{:02d}".format(int(match.group(1)))
        episode = "{:02d}".format(int(match.group(2)))

        return season, episode

    def extrametadata(self, episode):
        self.output["tvshow"] = self.output["season"] is not None and self.output["episode"] is not None
        if "validFrom" in episode:

            def _fix_broken_timezone_implementation(value):
                # cx_freeze cant include .zip file for dateutil and < py37 have issues with timezones with : in it
                if "+" in value and ":" == value[-3:-2]:
                    value = value[:-3] + value[-2:]
                return value

            validfrom = episode["validFrom"]
            if "+" in validfrom:
                date = time.mktime(
                    datetime.datetime.strptime(
                        _fix_broken_timezone_implementation(episode["validFrom"].replace("Z", "")),
                        "%Y-%m-%dT%H:%M:%S%z",
                    ).timetuple(),
                )
            else:
                date = time.mktime(
                    datetime.datetime.strptime(
                        _fix_broken_timezone_implementation(episode["validFrom"].replace("Z", "")),
                        "%Y-%m-%dT%H:%M:%S",
                    ).timetuple(),
                )
            self.output["publishing_datetime"] = int(date)

        self.output["title_nice"] = episode["parent"]["name"]

        try:
            t = episode["parent"]["image"]
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
            t = episode["image"]
        except KeyError:
            t = ""
        if isinstance(t, dict):
            url = "https://www.svtstatic.se/image/original/default/{id}/{changed}?format=auto&quality=100".format(**t)
            self.output["episodethumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["episodethumbnailurl"] = url

        if "longDescription" in episode["parent"]:
            self.output["showdescription"] = episode["parent"]["longDescription"]

        if "longDescription" in episode:
            self.output["episodedescription"] = episode["longDescription"]
