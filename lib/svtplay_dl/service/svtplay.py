# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import datetime
import hashlib
import json
import logging
import re
import time
from urllib.parse import parse_qs
from urllib.parse import quote_plus
from urllib.parse import urljoin
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import MetadataThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle
from svtplay_dl.subtitle import subtitle_probe
from svtplay_dl.utils.text import filenamify

URL_VIDEO_API = "https://api.svt.se/video/"
LIVE_CHANNELS = {
    "svtbarn": "ch-barnkanalen",
    "svt1": "ch-svt1",
    "svt2": "ch-svt2",
    "svt24": "ch-svt24",
    "kunskapskanalen": "ch-kunskapskanalen",
}


class Svtplay(Service, MetadataThumbMixin):
    supported_domains = ["svtplay.se", "svt.se", "beta.svtplay.se", "svtflow.se"]
    info_search_expr = r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>"
    access = None

    def get(self):
        parse = urlparse(self.url)
        if parse.netloc in ("www.svtplay.se", "svtplay.se"):
            if parse.path[:6] != "/video" and parse.path[:6] != "/klipp" and parse.path[:8] != "/kanaler":
                yield ServiceError("This mode is not supported anymore. Need the url with the video.")
                return

        query = parse_qs(parse.query)

        if "accessService" in query:
            self.access = query["accessService"]

        urldata = self.get_urldata()

        if parse.path[:8] == "/kanaler":
            ch = LIVE_CHANNELS[parse.path[parse.path.rfind("/") + 1 :]]
            _url = urljoin(URL_VIDEO_API, ch)
            res = self.http.get(_url)
            try:
                janson = res.json()
            except json.decoder.JSONDecodeError:
                yield ServiceError(f"Can't decode api request: {res.request.url}")
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
            if "data" in data_entry:
                entry = json.loads(data_entry["data"])
                for key, data in entry.items():
                    if key == "detailsPageByPath" and data and "smartStart" in data and data["smartStart"]:
                        video_data = data
                        vid = data["smartStart"]["videoSvtId"]
                        break

        if not vid:
            yield ServiceError("Can't find video id")
            return

        self.outputfilename(video_data)
        self.extrametadata(video_data)
        self.chaptersdata(video_data)

        res = self.http.get(URL_VIDEO_API + vid)
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError(f"Can't decode api request: {res.request.url}")
            return
        if res.status_code >= 400:
            yield ServiceError("Can't find any videos. Is it removed?")
            return
        videos = self._get_video(janson)
        yield from videos

    def _get_video(self, janson):
        entries = []
        subs = []

        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if "url" in i:
                    lang = None
                    subfix = None
                    if "label" in i:
                        lang = i["label"][:2].lower()
                    if "type" in i:
                        if "sdh" in i["type"]:
                            subfix = f"{lang}-caption"
                        else:
                            subfix = lang
                    for x in subtitle_probe(copy.copy(self.config), i["url"], subfix=subfix, output=self.output):
                        subs.append(x)

        if not janson["videoReferences"]:
            yield ServiceError("Media doesn't have any associated videos.")
            return

        drm = janson["rights"]["drmCopyProtection"]
        if not drm and "variants" in janson and "default" in janson["variants"]:
            if len(janson["videoReferences"]) == 0:
                yield ServiceError("Media doesn't have any associated videos.")
                return

            for videorfc in janson["videoReferences"]:
                params = {}
                special = False
                video_resolv_url = self.http.get(videorfc["resolve"]).json()["location"]
                params["manifestUrl"] = quote_plus(video_resolv_url)
                format = videorfc["format"]
                if "audioDescribed" in janson["variants"] and janson["variants"]["audioDescribed"]:
                    for audiodesc in janson["variants"]["audioDescribed"]["videoReferences"]:
                        if audiodesc["format"] == format:
                            special = True
                            audio_resolv_url = self.http.get(audiodesc["resolve"]).json()["location"]
                            params["manifestUrlAudioDescription"] = audio_resolv_url
                if "signInterpreted" in janson["variants"] and janson["variants"]["signInterpreted"]:
                    for signinter in janson["variants"]["signInterpreted"]["videoReferences"]:
                        if signinter["format"] == format:
                            special = True
                            audio_resolv_url = self.http.get(signinter["resolve"]).json()["location"]
                            params["manifestUrlSignLanguage"] = audio_resolv_url
                if special:
                    params = _dict_to_flatstr(params)
                    pl_url = f"https://api.svt.se/ditto/api/v1/web?{params}"
                else:
                    pl_url = videorfc["url"]

                if "hls-ts-full" == format:
                    continue
                if pl_url.find(".m3u8") > 0:
                    hls = hlsparse(self.config, self.http.request("get", pl_url), pl_url, output=self.output)
                    entries.append(hls)
                elif pl_url.find(".mpd") > 0:
                    mpd = dashparse(self.config, self.http.request("get", pl_url), pl_url, output=self.output)
                    entries.append(mpd)

        else:
            if "videoReferences" in janson:
                if len(janson["videoReferences"]) == 0:
                    yield ServiceError("Media doesn't have any associated videos.")
                    return

                for i in janson["videoReferences"]:
                    if "hls-ts-full" == i["format"]:
                        continue
                    if i["url"].find(".m3u8") > 0:
                        rdr_resp_url = self.http.get(i["resolve"]).json()["location"]
                        hls = hlsparse(self.config, self.http.request("get", rdr_resp_url), rdr_resp_url, output=self.output)
                        entries.append(hls)

        for entry in entries:
            for i in entry:
                if isinstance(i, subtitle):
                    subs.append(i)
                else:
                    yield i

        if check_exists(["sv", "sv-caption"], subs):
            for i in subs:
                if i.subfix == "sv-caption":
                    i.subfix = "sv"
                    yield i
        else:
            for i in subs:
                yield i

    def _lists(self):
        videos = []
        match = re.search(self.info_search_expr, self.get_urldata())
        if not match:
            logging.error("Can't find video info.")
            return videos
        janson = json.loads(match.group(1))
        data = None
        for data_entry in janson["props"]["urqlState"].values():
            if "data" in data_entry:
                entry = json.loads(data_entry["data"])
                if "selectionById" in entry:
                    data = entry

        if data:
            for i in data["selectionById"]["items"]:
                videos.append(urljoin("http://www.svtplay.se", i["item"]["urls"]["svtplay"]))
        return videos

    def _last_chance(self):
        videos = []
        match = re.search(self.info_search_expr, self.get_urldata())
        if not match:
            logging.error("Can't find video info.")
            return videos
        janson = json.loads(match.group(1))
        video_data = None
        for data_entry in janson["props"]["urqlState"].values():
            entry = json.loads(data_entry["data"])
            for key, data in entry.items():
                if key == "startForSvtPlay":
                    video_data = data
        if not video_data:
            return videos
        for section in video_data["selections"]:
            for i in section["items"]:
                videos.append(urljoin("http://www.svtplay.se", i["item"]["urls"]["svtplay"]))
        return videos

    def _genre(self):
        videos = []
        episodes = []
        singles = []
        parse = urlparse(self.url)
        url = f"https://www.svtplay.se{parse.path}?tab=all"
        data = self.http.get(url).text
        match = re.search(self.info_search_expr, data)
        if not match:
            logging.error("Can't find video info.")
            return episodes
        janson = json.loads(match.group(1))
        video_data = None
        for data_entry in janson["props"]["urqlState"].values():
            entry = json.loads(data_entry["data"])
            for key, data in entry.items():
                if key == "categoryPage":
                    if "lazyLoadedTabs" in data:
                        video_data = data["lazyLoadedTabs"]
        if not video_data:
            return episodes

        for lazytab in video_data:
            if lazytab["slug"] == "all":
                for module in lazytab["modules"]:
                    if "selection" in module:
                        for i in module["selection"]["items"]:
                            if i["item"]["__typename"] == "Single":
                                singles.append(urljoin("http://www.svtplay.se", i["item"]["urls"]["svtplay"]))
                            else:
                                videos.append(urljoin("http://www.svtplay.se", i["item"]["urls"]["svtplay"]))
        for i in videos:
            episodes.extend(self._all_episodes(i))
        if singles:
            episodes.extend(singles)
        return episodes

    def _all_episodes(self, url):
        parse = urlparse(url)
        tab = None
        videos = []
        if parse.query:
            query = parse_qs(parse.query)
            if "tabs" in query:
                tab = query["tabs"][0]

        data = self.http.get(url).text
        match = re.search(self.info_search_expr, data)
        if not match:
            logging.error("Can't find video info.")
            return videos

        janson = json.loads(match.group(1))
        video_data = None
        for data_entry in janson["props"]["urqlState"].values():
            if "data" in data_entry:
                entry = json.loads(data_entry["data"])
                for key, data in entry.items():
                    if key == "detailsPageByPath" and data and "smartStart" in data:
                        video_data = data
                        break

        collections = []
        if video_data is None:
            return videos
        if video_data["item"]["parent"]["__typename"] == "Single":
            videos.append(urljoin("http://www.svtplay.se", video_data["item"]["urls"]["svtplay"]))

        for i in video_data["modules"]:
            if tab:
                if tab == i["id"]:
                    collections.append(i)
            else:
                if i["id"] == "upcoming" or i["id"] == "related" or i["id"].startswith("details"):
                    continue
                elif self.config.get("include_clips") and "clips" in i["id"]:
                    collections.append(i)
                elif "clips" not in i["id"]:
                    collections.append(i)

        for i in collections:
            if not i["selection"]:
                continue
            for epi in i["selection"]["items"]:
                if epi["item"]["urls"]["svtplay"] not in videos:
                    videos.append(urljoin("http://www.svtplay.se", epi["item"]["urls"]["svtplay"]))
        return videos

    def find_all_episodes(self, config):
        parse = urlparse(self._url)

        episodes = []
        if re.search("^/sista-chansen", parse.path):
            episodes = self._last_chance()
        elif re.search("^/kategori", parse.path):
            episodes = self._genre()
        elif re.search("^/lista", parse.path):
            episodes = self._lists()
        else:
            episodes = self._all_episodes(self.url)

        if not episodes:
            logging.error("Can't find any videos.")
        else:
            if not self.config.get("reverse_list"):
                episodes = episodes[::-1]

            if config.get("all_last") > 0:
                return episodes[: config.get("all_last")]
        return episodes

    def outputfilename(self, data):
        name = None
        desc = None
        modulej = None

        for module in data["modules"]:
            if "analytics" in module and module["analytics"]["json"]["moduleType"] == "Details":
                modulej = module
        if modulej is None:
            return
        name = modulej["details"]["heading"]
        other = modulej["details"]["smartStart"]["item"]["videos"][0]["name"]
        vid = hashlib.sha256(modulej["details"]["smartStart"]["videoSvtId"].encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        elif name is None:
            name = other
            other = None
        elif other is None:
            pass

        season, episode = self.seasoninfo(data)
        if "accessibility" in data:
            if data["accessibility"] == "AudioDescribed":
                desc = "syntolkat"
            if data["accessibility"] == "SignInterpreted":
                desc = "teckentolkat"

        if not other:
            other = desc
        elif desc:
            other += f"-{desc}"

        self.output["title"] = filenamify(name)
        self.output["id"] = vid
        self.output["season"] = season
        self.output["episode"] = episode
        self.output["episodename"] = other

    def seasoninfo(self, data):
        season, episode = None, None

        season_nr = self._find_season(data)
        episode_nr = self._find_episode(data)

        if season_nr is None or episode_nr is None:
            return season, episode

        season = f"{int(season_nr):02d}"
        episode = f"{int(episode_nr):02d}"

        return season, episode

    def _find_season(self, data):
        modulej = None
        for module in data["modules"]:
            if "analytics" in module and module["analytics"]["json"]["moduleType"] == "Details":
                modulej = module
        if modulej is None:
            return
        match = re.search(r"/säsong (\d+)/", data["analytics"]["json"]["viewId"])
        if match:
            return match.group(1)

        match = re.search(r"-sasong-(\d+)-", data["item"]["urls"]["svtplay"])
        if match:
            return match.group(1)

        if "productionYear" in data["moreDetails"]:
            return data["moreDetails"]["productionYear"]

        return None

    def _find_episode(self, data):
        modulej = None
        for module in data["modules"]:
            if "analytics" in module and module["analytics"]["json"]["moduleType"] == "Details":
                modulej = module
        if modulej is None:
            return

        match = re.search(r"/avsnitt (\d+)", data["analytics"]["json"]["viewId"])
        if match:
            return match.group(1)

        match = re.search(r"Avsnitt (\d+)", data["item"]["name"])
        if match:
            return match.group(1)

        if "description" in data:
            match = re.search(r"Del (\d+) av (\d+)", data["description"])
            if match:
                return match.group(1)

        return None

    def extrametadata(self, episode):
        modulej = None
        for module in episode["modules"]:
            if "analytics" in module and module["analytics"]["json"]["moduleType"] == "Details":
                modulej = module
        if modulej is None:
            return
        self.output["tvshow"] = self.output["season"] is not None and self.output["episode"] is not None
        if "validFrom" in episode["item"]:

            def _fix_broken_timezone_implementation(value):
                # cx_freeze cant include .zip file for dateutil and < py37 have issues with timezones with : in it
                if "+" in value and ":" == value[-3:-2]:
                    value = value[:-3] + value[-2:]
                return value

            validfrom = episode["item"]["validFrom"]
            if "+" in validfrom:
                timeformat = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in episode["item"]["validFrom"] else "%Y-%m-%dT%H:%M:%S%z"
                date = time.mktime(
                    datetime.datetime.strptime(
                        _fix_broken_timezone_implementation(episode["item"]["validFrom"].replace("Z", "")),
                        timeformat,
                    ).timetuple(),
                )
            else:
                date = time.mktime(
                    datetime.datetime.strptime(
                        _fix_broken_timezone_implementation(episode["item"]["validFrom"].replace("Z", "")),
                        "%Y-%m-%dT%H:%M:%S",
                    ).timetuple(),
                )
            self.output["publishing_datetime"] = int(date)

        self.output["title_nice"] = modulej["details"]["heading"]

        try:
            t = episode["item"]["parent"]["image"]["wide"]
        except KeyError:
            t = ""
        if isinstance(t, dict):
            url = f"https://www.svtstatic.se/image/original/default/{t['id']}/{t['changed']}?format=auto&quality=100"
            self.output["showthumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["showthumbnailurl"] = url
        try:
            t = episode["images"]["wide"]
        except KeyError:
            t = ""
        if isinstance(t, dict):
            url = f"https://www.svtstatic.se/image/original/default/{t['id']}/{t['changed']}?format=auto&quality=100"
            self.output["episodethumbnailurl"] = url
        elif t:
            # Get the image if size/format is not specified in the URL set it to large
            url = t.format(format="large")
            self.output["episodethumbnailurl"] = url

        if "longDescription" in episode["item"]["parent"]:
            self.output["showdescription"] = episode["item"]["parent"]["longDescription"]

        if "description" in episode:
            self.output["episodedescription"] = episode["description"]

    def chaptersdata(self, video_data):
        chapters = []
        for chapter in video_data["highlights"]:
            chap = {"title": chapter["name"], "startime": chapter["positionInSeconds"] * 1000}
            chapters.append(chap)
        self.output["chapters"] = chapters


def _dict_to_flatstr(flat):
    text = ""
    for i in flat:
        text += f"{i}={flat[i]}&"
    return text


def check_exists(valuea, valueb):
    return all(any(x == y.subfix for y in valueb) for x in valuea)
