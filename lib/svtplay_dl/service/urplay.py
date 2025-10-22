# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin
from urllib.parse import urlparse

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
        match = re.search(r"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", urldata)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        parse = urlparse(self.url)
        data = unescape(match.group(1))
        jsondata = json.loads(data)
        if "/serie/" in parse.path:
            jsondata = jsondata["props"]["pageProps"]["productData"]["uraccessPrograms"][0]
            vid_url = f"https://urplay.se/{jsondata['link']}"
            vid_data = self.http.get(vid_url).text
            match = re.search(r"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", vid_data)
            data = unescape(match.group(1))
            jsondata = json.loads(data)

        vid = jsondata["props"]["pageProps"]["productData"]["id"]
        jsondata = jsondata["props"]["pageProps"]["productData"]

        res = self.http.get(f"https://media-api.urplay.se/config-streaming/v1/urplay/sources/{vid}")
        if res.status_code == 403:
            yield ServiceError("The video is geoblocked. Can't download this video")
            return

        self.outputfilename(jsondata, urldata)

        if "dash" in res.json()["sources"]:
            yield from dashparse(
                self.config,
                self.http.request("get", res.json()["sources"]["dash"]),
                res.json()["sources"]["dash"],
                output=self.output,
            )
        if "hls" in res.json()["sources"]:
            yield from hlsparse(self.config, self.http.request("get", res.json()["sources"]["hls"]), res.json()["sources"]["hls"], output=self.output)

        self.outputfilename(jsondata, urldata)

    def find_all_episodes(self, config):
        episodes = []

        match = re.search(r"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", self.get_urldata())
        if not match:
            logging.error("Can't find video info.")
            return episodes

        jsondata = json.loads(match.group(1))
        seasons = jsondata["props"]["pageProps"]["productData"]["seasonLabels"]
        build = jsondata["buildId"]

        parse = urlparse(self.url)
        url = f"https://{parse.netloc}{parse.path}"
        episodes.append(url)
        for season in seasons:
            res = self.http.get(
                f'https://urplay.se/_next/data/{build}{season["link"]}.json?productType={jsondata["query"]["productType"]}&id={jsondata["props"]["pageProps"]["productData"]["id"]}',
            )
            for episode in res.json()["pageProps"]["productData"]["programs"]:
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
        if "description" in data:
            self.output["episodedescription"] = data["description"]
        if "publishedAt" in data:
            self.output["publishing_datetime"] = datetime.fromisoformat(data["publishedAt"]).timestamp()

        self.output["episodethumbnailurl"] = data["image"]["1280x720"]

        if "seriesLabel" in data:
            seasonmatch = re.search(r"S.song (\d+)", data["seriesLabel"])
            if seasonmatch:
                self.output["season"] = seasonmatch.group(1)
        else:
            self.output["season"] = "1"  # No season info - probably show without seasons

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])
