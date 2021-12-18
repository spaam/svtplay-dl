# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import logging
import re
from html import unescape
from urllib.parse import urljoin

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.http import download_thumbnails


class Urplay(Service, OpenGraphThumbMixin):
    supported_domains = ["urplay.se", "ur.se", "betaplay.ur.se", "urskola.se"]

    def get(self):
        urldata = self.get_urldata()
        match = re.search(r"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", urldata)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        data = unescape(match.group(1))
        jsondata = json.loads(data)

        res = self.http.get("https://streaming-loadbalancer.ur.se/loadbalancer.json")
        loadbalancer = res.json()["redirect"]
        jsondata = jsondata["props"]["pageProps"]["program"]

        self.outputfilename(jsondata, urldata)

        for streaminfo in jsondata["streamingInfo"].keys():
            stream = jsondata["streamingInfo"][streaminfo]

            if streaminfo == "raw":
                if "sd" in stream:
                    url = f"https://{loadbalancer}/{stream['sd']['location']}playlist.m3u8"
                    yield from hlsparse(self.config, self.http.request("get", url), url, output=self.output)
                if "hd" in stream:
                    url = f"https://{loadbalancer}/{stream['hd']['location']}playlist.m3u8"
                    yield from hlsparse(self.config, self.http.request("get", url), url, output=self.output)
            if not (self.config.get("get_all_subtitles")) and streaminfo == "sweComplete":
                yield subtitle(copy.copy(self.config), "wrst", stream["tt"]["location"].replace(".tt", ".vtt"), output=self.output)

            if self.config.get("get_all_subtitles") and "tt" in stream:
                label = stream["tt"]["language"]
                if stream["tt"]["scope"] != "complete":
                    label = f"{label}-{stream['tt']['scope']}"
                yield subtitle(copy.copy(self.config), "wrst", stream["tt"]["location"].replace(".tt", ".vtt"), label, output=copy.copy(self.output))

    def find_all_episodes(self, config):
        episodes = []

        match = re.search(r"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", self.get_urldata())
        if not match:
            logging.error("Can't find video info.")
            return episodes

        data = unescape(match.group(1))
        jsondata = json.loads(data)
        seasons = jsondata["props"]["pageProps"]["superSeriesSeasons"]
        if seasons:
            for season in seasons:
                res = self.http.get(f'https://urplay.se/api/v1/series?id={season["id"]}')
                for episode in res.json()["programs"]:
                    episodes.append(urljoin("https://urplay.se", episode["link"]))
        else:
            for episode in jsondata["props"]["pageProps"]["accessibleEpisodes"]:
                episodes.append(urljoin("https://urplay.se", episode["link"]))
        episodes_new = []
        n = 0
        for i in episodes:
            if n == config.get("all_last"):
                break
            if i not in episodes_new:
                episodes_new.append(i)
            n += 1
        return episodes_new

    def outputfilename(self, data, urldata):
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

        self.output["episodethumbnailurl"] = data["image"]["1280x720"]

        seasonmatch = re.search(r"data-testid=\"season-name-label\">S.song (\d+)...<\/span", urldata)
        if seasonmatch:
            self.output["season"] = seasonmatch.group(1)
        else:
            self.output["season"] = "1"  # No season info - probably show without seasons

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])
