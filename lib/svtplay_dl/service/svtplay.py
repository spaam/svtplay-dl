# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import json
import hashlib
import logging
from urllib.parse import urljoin, urlparse, parse_qs
from operator import itemgetter

from svtplay_dl.service import Service, MetadataThumbMixin
from svtplay_dl.utils.text import filenamify
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError

URL_VIDEO_API = "http://api.svt.se/videoplayer-api/video/"


class Svtplay(Service, MetadataThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'beta.svtplay.se', 'svtflow.se']

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

        if parse.path[:8] == "/kanaler":
            res = self.http.get(URL_VIDEO_API + "ch-{0}".format(parse.path[9:]))
            try:
                janson = res.json()
            except json.decoder.JSONDecodeError:
                yield ServiceError("Can't decode api request: {0}".format(res.request.url))
                return
            videos = self._get_video(janson)
            self.config.set("live", True)
            for i in videos:
                yield i
            return

        match = re.search(r"__svtplay'] = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video info.")
            return
        janson = json.loads(match.group(1))["videoPage"]

        if "programTitle" not in janson["video"]:
            yield ServiceError("Can't find any video on that page.")
            return

        if self.access:
            for i in janson["video"]["versions"]:
                if i["accessService"] == self.access:
                    url = urljoin("http://www.svtplay.se", i["contentUrl"])
                    res = self.http.get(url)
                    match = re.search("__svtplay'] = ({.*});", res.text)
                    if not match:
                        yield ServiceError("Can't find video info.")
                        return
                    janson = json.loads(match.group(1))["videoPage"]

        self.outputfilename(janson["video"])
        self.extrametadata(janson)

        if "programVersionId" in janson["video"]:
            vid = janson["video"]["programVersionId"]
        else:
            vid = janson["video"]["id"]
        res = self.http.get(URL_VIDEO_API + vid)
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {0}".format(res.request.url))
            return
        videos = self._get_video(janson)
        for i in videos:
            yield i

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

                elif i["format"] == "hds":
                    match = re.search(r"\/se\/secure\/", i["url"])
                    if not match:
                        streams = hdsparse(self.config, self.http.request("get", i["url"], params={"hdcore": "3.7.0"}),
                                           i["url"], output=self.output)
                        if alt:
                            alt_streams = hdsparse(self.config, self.http.request("get", alt.request.url, params={"hdcore": "3.7.0"}),
                                                   alt.request.url, output=self.output)
                elif i["format"] == "dash264" or i["format"] == "dashhbbtv":
                    streams = dashparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    if alt:
                        alt_streams = dashparse(self.config, self.http.request("get", alt.request.url),
                                                alt.request.url, output=self.output)

                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
                if alt_streams:
                    for n in list(alt_streams.keys()):
                        yield alt_streams[n]

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
        self._last_chance(videos, page, pages)
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
        match = re.search("__svtplay'] = ({.*});", self.get_urldata())
        if re.search("sista-chansen", parse.path):
            videos = self._last_chance(videos, 1)
        elif not match:
            logging.error("Couldn't retrieve episode list.")
            return
        else:
            dataj = json.loads(match.group(1))
            if re.search("/genre", parse.path):
                videos = self._genre(dataj)
            else:
                if parse.query:
                    query = parse_qs(parse.query)
                    if "tab" in query:
                        tab = query["tab"][0]

                if dataj["relatedVideoContent"]:
                    items = dataj["relatedVideoContent"]["relatedVideosAccordion"]
                    for i in items:
                        if tab:
                            if i["slug"] == tab:
                                videos = self.videos_to_list(i["videos"], videos)
                        else:
                            if "klipp" not in i["slug"] and "kommande" not in i["slug"]:
                                videos = self.videos_to_list(i["videos"], videos)
                        if self.config.get("include_clips"):
                            if i["slug"] == "klipp":
                                videos = self.videos_to_list(i["videos"], videos)

        episodes = [urljoin("http://www.svtplay.se", x) for x in videos]

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last"):]
        return episodes

    def videos_to_list(self, lvideos, videos):
        if "episodeNumber" in lvideos[0] and lvideos[0]["episodeNumber"]:
            lvideos = sorted(lvideos, key=itemgetter('episodeNumber'))
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
        if "programTitle" in data and data["programTitle"]:
            name = filenamify(data["programTitle"])
        elif "titleSlug" in data and data["titleSlug"]:
            name = filenamify(data["titleSlug"])
        other = data["title"]

        if "programVersionId" in data:
            vid = str(data["programVersionId"])
        else:
            vid = str(data["id"])
        id = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        elif name is None:
            name = other
            other = None

        season, episode = self.seasoninfo(data)
        if "accessService" in data:
            if data["accessService"] == "audioDescription":
                desc = "syntolkat"
            if data["accessService"] == "signInterpretation":
                desc = "teckentolkat"

        if not other:
            other = desc
        elif desc:
            other += "-{}".format(desc)

        self.output["title"] = name
        self.output["id"] = id
        self.output["season"] = season
        self.output["episode"] = episode
        self.output["episodename"] = other

    def seasoninfo(self, data):
        season, episode = None, None
        if "season" in data and data["season"]:
            season = "{:02d}".format(data["season"])
            if int(season) == 0:
                season = None
        if "episodeNumber" in data and data["episodeNumber"]:
            episode = "{:02d}".format(data["episodeNumber"])
            if int(episode) == 0:
                episode = None
        if episode is not None and season is None:
            # Missing season, happens for some barnkanalen shows assume first and only
            season = "01"
        return season, episode

    def extrametadata(self, data):
        self.output["tvshow"] = (self.output["season"] is not None and self.output["episode"] is not None)
        try:
            self.output["publishing_datetime"] = data["video"]["broadcastDate"] / 1000
        except KeyError:
            pass
        try:
            title = data["video"]["programTitle"]
            self.output["title_nice"] = title
        except KeyError:
            title = data["video"]["titleSlug"]
            self.output["title_nice"] = title

        try:
            t = data['state']["titleModel"]["thumbnail"]
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
            t = data["video"]["thumbnailXL"]
        except KeyError:
            try:
                t = data["video"]["thumbnail"]
            except KeyError:
                t = ""
        if isinstance(t, dict):
            url = "https://www.svtstatic.se/image/original/default/{id}/{changed}?format=auto&quality=100".format(**t)
            self.output["episodethumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["episodethumbnailurl"] = url
        try:
            self.output["showdescription"] = data['state']["titleModel"]["description"]
        except KeyError:
            pass
        try:
            self.output["episodedescription"] = data["video"]["description"]
        except KeyError:
            pass
