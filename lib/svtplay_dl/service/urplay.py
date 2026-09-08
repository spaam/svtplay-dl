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

        seasondata = self._get_seasondata(urldata)
        if seasondata:
            superseries = seasondata["superSeriesSeasons"]
            if isinstance(superseries, list) and superseries:
                # Show split over several series ids, one per season.
                seasons = [season["id"] for season in superseries]
            elif isinstance(seasondata["seriesId"], int):
                seasons.append(seasondata["seriesId"])

        if not seasons:
            episodes.append(self.url)

        for seriesid in seasons:
            res = self.http.get(
                f"https://urplay.se/api/v1/season_episodes?seriesId={seriesid}",
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

        # The RSC payload encodes a missing value as the string "$undefined",
        # so check the type instead of just truthiness.
        series = data.get("series")
        serieslabel = series.get("label") if isinstance(series, dict) else None
        if serieslabel:
            seasonmatch = re.search(r"S.song (\d+)", serieslabel)
            if seasonmatch:
                self.output["season"] = seasonmatch.group(1)
        else:
            if self.output["episode"]:
                self.output["season"] = "1"  # No season info - probably show without seasons

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])

    def _get_janson(self, urldata):
        return self._find_flight_data(urldata, ["isAudio", "currentProduct"])

    def _get_seasondata(self, urldata):
        return self._find_flight_data(urldata, ["superSeriesSeasons", "seriesId"])

    def _find_flight_data(self, urldata, required_keys):
        # The RSC payload is streamed as a series of __next_f.push() calls that each
        # append a chunk to one big buffer. A single flight row can be split across
        # two pushes, so glue everything together before splitting it into rows.
        buffer = ""
        for chunk in re.findall(r"__next_f\.push\((\[.*?\])\)</scri", urldata, re.DOTALL):
            try:
                janson = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            for item in janson:
                if isinstance(item, str):
                    buffer += item

        # Each row looks like "<hex id>:<payload>", one per line.
        for row in re.split(r"\n(?=[0-9a-f]+:)", buffer):
            index = row.find(":")
            if index < 0:
                continue
            rawdata = row[index + 1 :]
            if not rawdata.startswith(("[", "{")):
                continue
            try:
                json_raw = json.loads(rawdata)
            except json.JSONDecodeError:
                continue
            result = self.find_dict_with_keys(json_raw, required_keys)
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
