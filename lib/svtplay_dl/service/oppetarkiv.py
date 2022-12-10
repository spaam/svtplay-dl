# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import hashlib
import logging
import re
from urllib.parse import parse_qs
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe
from svtplay_dl.utils.text import decode_html_entities


class OppetArkiv(Service, OpenGraphThumbMixin):
    supported_domains = ["oppetarkiv.se"]

    def get(self):
        vid = self.find_video_id()
        if vid is None:
            yield ServiceError("Cant find video id for this video")
            return

        url = f"http://api.svt.se/videoplayer-api/video/{vid}"
        data = self.http.request("get", url)
        if data.status_code == 404:
            yield ServiceError(f"Can't get the json file for {url}")
            return

        data = data.json()
        if "live" in data:
            self.config.set("live", data["live"])

        self.outputfilename(data)

        if "subtitleReferences" in data:
            for i in data["subtitleReferences"]:
                yield from subtitle_probe(copy.copy(self.config), i["url"], output=self.output)

        if len(data["videoReferences"]) == 0:
            yield ServiceError("Media doesn't have any associated videos (yet?)")
            return

        for i in data["videoReferences"]:
            parse = urlparse(i["url"])
            query = parse_qs(parse.query)
            if i["format"] == "hls" or i["format"] == "ios":
                yield from hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                if "alt" in query and len(query["alt"]) > 0:
                    alt = self.http.get(query["alt"][0])
                    if alt:
                        yield from hlsparse(self.config, self.http.request("get", alt.request.url), alt.request.url, output=self.output)
            if i["format"] == "dash264" or i["format"] == "dashhbbtv":
                yield from dashparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                if "alt" in query and len(query["alt"]) > 0:
                    alt = self.http.get(query["alt"][0])
                    if alt:
                        yield from dashparse(self.config, self.http.request("get", alt.request.url), alt.request.url, output=self.output)

    def find_video_id(self):
        match = re.search('data-video-id="([^"]+)"', self.get_urldata())
        if match:
            return match.group(1)
        return None

    def find_all_episodes(self, config):
        episodes = []
        page = 1
        data = self.get_urldata()
        match = re.search(r'"/etikett/titel/([^"/]+)', data)
        if match is None:
            match = re.search(r'"http://www.oppetarkiv.se/etikett/titel/([^/]+)/', self.url)
            if match is None:
                logging.error("Couldn't find title")
                return episodes
        program = match.group(1)

        n = 0
        if config.get("all_last") > 0:
            sort = "tid_fallande"
        else:
            sort = "tid_stigande"

        while True:
            url = f"http://www.oppetarkiv.se/etikett/titel/{program}/?sida={page}&sort={sort}&embed=true"
            data = self.http.request("get", url)
            if data.status_code == 404:
                break

            data = data.text
            regex = re.compile(r'href="(/video/[^"]+)"')
            for match in regex.finditer(data):
                if n == self.config.get("all_last"):
                    break
                episodes.append(f"http://www.oppetarkiv.se{match.group(1)}")
                n += 1
            page += 1

        return episodes

    def outputfilename(self, data):
        vid = hashlib.sha256(data["programVersionId"].encode("utf-8")).hexdigest()[:7]
        self.output["id"] = vid

        datatitle = re.search('data-title="([^"]+)"', self.get_urldata())
        if not datatitle:
            return
        datat = decode_html_entities(datatitle.group(1))
        self.output["title"] = self.name(datat)
        self.seasoninfo(datat)

    def seasoninfo(self, data):
        match = re.search(r"S.song (\d+) - Avsnitt (\d+)", data)
        if match:
            self.output["season"] = int(match.group(1))
            self.output["episode"] = int(match.group(2))
        else:
            match = re.search(r"Avsnitt (\d+)", data)
            if match:
                self.output["episode"] = int(match.group(1))

    def name(self, data):
        if data.find(" - S.song") > 0:
            title = data[: data.find(" - S.song")]
        else:
            if data.find(" - Avsnitt") > 0:
                title = data[: data.find(" - Avsnitt")]
            else:
                title = data
        return title
