# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
import sys
from datetime import datetime
from urllib.parse import urljoin

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.utils.http import download_thumbnails


class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ["urplay.se", "ur.se", "betaplay.ur.se", "urskola.se"]

    def get(self):
        urldata = self.get_urldata()

        jsondata = self._get_janson(urldata)
        if not jsondata:
            yield ServiceError("Could not find video data.")
            return

        vid = jsondata["currentProduct"]["id"]

        res = self.http.get(f"https://media-api.urplay.se/config-streaming/v1/urplay/sources/{vid}")
        if res.status_code == 403:
            yield ServiceError("The video is geoblocked. Can't download this video")
            return

        self.outputfilename(jsondata["currentProduct"])

        if "dash" in res.json()["sources"]:
            yield from dashparse(
                self.config,
                self.http.request("get", res.json()["sources"]["dash"]),
                res.json()["sources"]["dash"],
                output=self.output,
            )
        if "hls" in res.json()["sources"]:
            yield from hlsparse(self.config, self.http.request("get", res.json()["sources"]["hls"]), res.json()["sources"]["hls"], output=self.output)

    def find_all_episodes(self, config):
        episodes = []
        seasons = []

        urldata = self.get_urldata()
        jsondata = self._get_janson(urldata)

        if not jsondata:
            logging.error("Can't find video info.")
            return episodes

        if "program" in jsondata and "series" in jsondata["program"] and jsondata["program"]["series"]:
            if "seasonLabels" in jsondata["program"]["series"]:
                if jsondata["program"]["series"]["seasonLabels"]:
                    seasons = jsondata["program"]["series"]["seasonLabels"]
                else:
                    seasons.append({"id": jsondata["program"]["series"]["id"]})
        else:
            episodes.append(self.url)

        for season in seasons:
            res = self.http.get(
                f'https://urplay.se/api/v1/seasonEpisodes?seriesId={season["id"]}',
            )
            for episode in res.json()["accessibleEpisodes"]:
                url = urljoin("https://urplay.se", episode["link"])
                if url not in episodes:
                    episodes.append(url)
        episodes_new = []
        n = 0
        for i in episodes:
            if n == config.get("all_last"):
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new

    def outputfilename(self, data):
        if "seriesTitle" in data:
            self.output["title"] = data["seriesTitle"]
            self.output["title_nice"] = data["seriesTitle"]
        if "episodeNumber" in data and data["episodeNumber"]:
            self.output["episode"] = str(data["episodeNumber"])
        if "title" in data:
            if self.output["title"] is None:
                self.output["title"] = data["title"]
            else:
                self.output["episodename"] = data["title"]
        if "id" in data and data["id"]:
            self.output["id"] = str(data["id"])
        if "description" in data:
            self.output["episodedescription"] = data["description"]
        if "publishedAt" in data:
            published = data["publishedAt"]
            if sys.version_info < (3, 12):  # 3.11 fix
                published = published.replace("Z", "+00:00")
            self.output["publishing_datetime"] = datetime.fromisoformat(published).timestamp()

        self.output["episodethumbnailurl"] = data["image"]["1280x720"]

        if "seriesLabel" in data and data["seriesLabel"]:
            seasonmatch = re.search(r"S.song (\d+)", data["seriesLabel"])
            if seasonmatch:
                self.output["season"] = seasonmatch.group(1)
        else:
            if self.output["episode"]:
                self.output["season"] = "1"  # No season info - probably show without seasons

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])

    def _get_janson(self, urldata):
        match = re.findall(r"__next_f\.push\((.+?)\)</scri", urldata, re.DOTALL)
        for i in match:
            janson = json.loads(i)
            for jsonlist in janson:
                if isinstance(jsonlist, str):
                    index = jsonlist.find(":")
                    if index > 0:
                        if jsonlist[index + 1 :].startswith("["):
                            rawdata = jsonlist[index + 1 :]
                            try:
                                json_raw = json.loads(rawdata)
                            except json.JSONDecodeError:
                                continue
                            result = self.find_dict_with_keys(json_raw, ["isAudio", "currentProduct"])

                            if result:
                                return result

        return None

    def find_dict_with_keys(self, obj, required_keys):
        if isinstance(obj, dict):
            if all(k in obj for k in required_keys):
                return obj
            for value in obj.values():
                result = self.find_dict_with_keys(value, required_keys)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self.find_dict_with_keys(item, required_keys)
                if result is not None:
                    return result
        return None
