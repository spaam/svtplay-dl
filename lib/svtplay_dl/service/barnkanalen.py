# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import hashlib
import json
import logging
import re
from urllib.parse import parse_qs
from urllib.parse import urljoin
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.utils.text import filenamify


class Barnkanalen(Svtplay):
    supported_domains = ["svt.se"]
    supported_path = "/barnkanalen"

    @classmethod
    def handles(cls, url):
        urlp = urlparse(url)

        correctpath = urlp.path.startswith(cls.supported_path)
        if urlp.netloc in cls.supported_domains and correctpath:
            return True

        # For every listed domain, try with www. subdomain as well.
        if urlp.netloc in ["www." + x for x in cls.supported_domains] and correctpath:
            return True

        return False

    def get(self):
        parse = urlparse(self.url)

        query = parse_qs(parse.query)
        self.access = None
        if "accessService" in query:
            self.access = query["accessService"]

        match = re.search("__barnplay'] = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))["context"]["dispatcher"]["stores"]["ApplicationStateStore"]["data"]
        if "episodeModel" not in janson["categoryStateCache"]["karaktarer"]:
            yield ServiceError("No videos found")
            return

        janson["video"] = janson["categoryStateCache"]["karaktarer"]["episodeModel"]

        if "title" not in janson["video"]:
            yield ServiceError("Can't find any video on that page.")
            return

        if "live" in janson["video"]:
            self.config.set("live", janson["video"]["live"])

        self.outputfilename(janson["video"])
        self.extrametadata(janson)

        if "programVersionId" in janson["video"]:
            vid = janson["video"]["programVersionId"]
        else:
            vid = janson["video"]["id"]
        res = self.http.get("http://api.svt.se/videoplayer-api/video/{}".format(vid))
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {}".format(res.request.url))
            return
        videos = self._get_video(janson)
        yield from videos

    def find_all_episodes(self, config):
        videos = []
        match = re.search("__barnplay'] = ({.*});", self.get_urldata())
        if not match:
            logging.error("Couldn't retrieve episode list.")
            return
        else:
            dataj = json.loads(match.group(1))
            dataj = dataj["context"]["dispatcher"]["stores"]["EpisodesStore"]
            showId = list(dataj["data"].keys())[0]
            items = dataj["data"][showId]["episodes"]
            for i in items:
                program = i
                videos = self.videos_to_list(program, videos)
            videos.reverse()

        episodes = [urljoin("http://www.svt.se", x) for x in videos]

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes

    def videos_to_list(self, lvideos, videos):
        url = self.url + "/" + str(lvideos["id"])
        parse = urlparse(url)
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
        self.output["tvshow"] = self.output["season"] is not None and self.output["episode"] is not None
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
            t = data["state"]["titleModel"]["thumbnail"]
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
            self.output["showdescription"] = data["state"]["titleModel"]["description"]
        except KeyError:
            pass
        try:
            self.output["episodedescription"] = data["video"]["description"]
        except KeyError:
            pass
