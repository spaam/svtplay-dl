# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103
import copy
import hashlib
import json
import logging
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.hls import M3U8
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


country = {".se": "sv", ".dk": "da", ".no": "no"}


class Viaplay(Service, OpenGraphThumbMixin):
    supported_domains = [
        "tv3play.ee",
        "tv3play.lv",
        "tv3play.lt",
        "tvplay.lv",
        "viagame.com",
        "juicyplay.se",
        "viafree.se",
        "viafree.dk",
        "viafree.no",
        "viafree.fi",
        "play.tv3.lt",
        "tv3play.tv3.ee",
        "tvplay.skaties.lv",
    ]

    def get(self):
        login = self._login()
        if not login:
            yield ServiceError("You need to login")
            return

        data = self.get_urldata()
        match = re.search('}}}},("staticPages".*}}); windo', data)
        if not match:
            yield ServiceError("Cant find necessary info")
            return

        janson = json.loads("{}{}".format("{", match.group(1)))
        video = None
        for play in janson["page"]["blocks"]:
            if "componentName" in play and play["componentName"] == "player":
                video = play
                break

        if not video:
            yield ServiceError("Can't find video")
            return

        self._autoname(video)

        if "subtitles" in video["_embedded"]["program"] and "subtitlesWebvtt" in video["_embedded"]["program"]["subtitles"]:
            if "m3u8" in video["_embedded"]["program"]["subtitles"]["subtitlesWebvtt"]:
                m3u8s = M3U8(self.http.get(video["_embedded"]["program"]["subtitles"]["subtitlesWebvtt"]).text)
                yield subtitle(
                    copy.copy(self.config),
                    "wrstsegment",
                    video["_embedded"]["program"]["subtitles"]["subtitlesWebvtt"],
                    output=copy.copy(self.output),
                    m3u8=m3u8s,
                )
            else:
                yield subtitle(copy.copy(self.config), "wrst", video["_embedded"]["program"]["subtitles"]["subtitlesWebvtt"], output=self.output)

        res = self.http.get(video["_embedded"]["program"]["_links"]["streamLink"]["href"])
        janson = res.json()
        stream = janson["embedded"]["prioritizedStreams"][0]["links"]["stream"]

        if video["_embedded"]["program"]["_links"]["streamLink"]:
            streams = hlsparse(
                self.config,
                self.http.request("get", stream["href"]),
                stream["href"],
                output=self.output,
                authorization=f"MTG-AT {self.token}",
            )
            for n in list(streams.keys()):
                yield streams[n]
        if "subtitles" in janson["embedded"] and len(janson["embedded"]["subtitles"]) > 0:
            lang = re.search(r"(\.\w\w)$", urlparse(self.url).netloc).group(1)
            if lang in country:
                language = country[lang]
            else:
                language = None

            if not self.config.get("get_all_subtitles"):
                if not language:
                    yield subtitle(copy.copy(self.config), "wrst", janson["embedded"]["subtitles"][0]["link"]["href"], output=self.output)
                else:
                    for i in janson["embedded"]["subtitles"]:
                        if i["data"]["language"] == language:
                            yield subtitle(copy.copy(self.config), "wrst", i["link"]["href"], output=self.output)

            else:
                for i in janson["embedded"]["subtitles"]:
                    yield subtitle(copy.copy(self.config), "wrst", i["link"]["href"], i["data"]["language"], output=copy.copy(self.output))

    def find_all_episodes(self, config):
        episodes = []
        parse = urlparse(self.url)
        data = self.get_urldata()
        match = re.search('}}}},("staticPages".*}}); windo', data)
        if not match:
            logging.error("Cant find necessary info")
            return

        janson = json.loads("{}{}".format("{", match.group(1)))
        seasons = []

        if janson["page"]["pageType"] == "player":
            res = self.http.get("{}://{}{}".format(parse.scheme, parse.netloc, janson["page"]["blocks"][0]["_links"]["back"]["publicPath"]))
            data = res.text
            match = re.search('}}}},("staticPages".*}}); windo', data)
            if not match:
                logging.error("Cant find necessary info")
                return

            janson = json.loads("{}{}".format("{", match.group(1)))

        for i in janson["page"]["blocks"]:
            if i["slug"] == "series_header" and "seasons" in i["seriesHeader"]:
                for n in i["seriesHeader"]["seasons"]:
                    seasons.append(n["_links"]["season"]["href"])
                break

        videos_tmp = []
        clips = []
        for season in seasons:
            res = self.http.get(season)
            janson = res.json()

            groups = None
            for i in janson["_embedded"]["viafreeBlocks"]:
                if i["componentName"] == "groups":
                    groups = i
                    break

            if groups:
                for i in groups["_embedded"]["blocks"][0]["_embedded"]["programs"]:
                    if i["type"] == "episode":
                        if i["episode"]["episodeNumber"]:
                            videos_tmp.append(
                                [
                                    int("{}{}".format(i["episode"]["seasonNumber"], i["episode"]["episodeNumber"])),
                                    "{}://{}{}".format(parse.scheme, parse.netloc, i["publicPath"]),
                                ],
                            )
                        elif config.get("include_clips"):
                            clips.append("{}://{}{}".format(parse.scheme, parse.netloc, i["publicPath"]))
                    else:
                        episodes.append("{}://{}{}".format(parse.scheme, parse.netloc, i["publicPath"]))
        if videos_tmp:
            for i in sorted(videos_tmp, key=lambda x: x[0]):
                episodes.append(i[1])

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]

        if clips:
            episodes.extend(clips)

        return sorted(episodes)

    def _autoname(self, dataj):
        typ = dataj["_embedded"]["program"]["type"]
        title = dataj["_embedded"]["program"]["title"]

        vid = dataj["_embedded"]["program"]["guid"]
        if re.search("-", vid):  # in sports they have "-" in the id..
            vid = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]
        self.output["id"] = vid

        if typ == "episode":
            program = dataj["_embedded"]["program"][typ]["seriesTitle"]
            self.output["season"] = dataj["_embedded"]["program"][typ]["seasonNumber"]
            self.output["episode"] = dataj["_embedded"]["program"][typ]["episodeNumber"]
            self.output["episodename"] = title
        elif typ == "clip":
            program = dataj["_embedded"]["program"]["episode"]["seriesTitle"]
            self.output["season"] = dataj["_embedded"]["program"]["episode"]["seasonNumber"]
            self.output["episodename"] = title
        else:
            program = title

        self.output["title"] = program

    def _login(self):
        res = self.http.post(
            "https://viafree.mtg-api.com/identity/viafree/auth/pwd/sessions",
            json={"email": self.config.get("username"), "password": self.config.get("password")},
            headers={"Accept": "Application/json"},
        )

        if res.status_code < 400:
            self.userID = res.json()["data"]["userData"]["userId"]
            self.token = res.json()["data"]["accessToken"]
            return True
        return False
