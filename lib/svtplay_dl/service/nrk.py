# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import logging
import re
from urllib.parse import urljoin

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe


class Nrk(Service, OpenGraphThumbMixin):
    supported_domains = ["nrk.no", "tv.nrk.no", "p3.no", "tv.nrksuper.no"]

    def get(self):
        self.video_id = None
        match = re.search('({"initialState.*})', self.get_urldata())
        if match:
            self.janson = json.loads(match.group(1))
        else:
            yield ServiceError("Can't find video id.")
            return

        if "selectedEpisodePrfId" in self.janson["initialState"]:
            self.video_id = self.janson["initialState"]["selectedEpisodePrfId"]
            self.outputfilename()
        elif "program" in self.janson["initialState"]:
            self.video_id = self.janson["initialState"]["program"]["prfId"]
        if not self.video_id:
            yield ServiceError("Can't find video id.")
            return

        dataurl = f"https://psapi.nrk.no/playback/manifest/program/{self.video_id}?eea-portability=true"
        janson = self.http.request(
            "get",
            dataurl,
            headers={"Accept": "application/vnd.nrk.psapi+json; version=9; player=tv-player; device=player-core"},
        ).json()

        if janson["playable"]:
            if janson["playable"]["assets"][0]["format"] == "HLS":
                yield from hlsparse(
                    self.config,
                    self.http.request("get", janson["playable"]["assets"][0]["url"]),
                    janson["playable"]["assets"][0]["url"],
                    output=self.output,
                )

            # Check if subtitles are available
            for sub in janson["playable"]["subtitles"]:
                if sub["defaultOn"]:
                    yield from subtitle_probe(copy.copy(self.config), sub["webVtt"], output=self.output)

    def find_all_episodes(self, options):
        episodes = []
        janson = None
        match = re.search('({"initialState.*})', self.get_urldata())
        if match:
            janson = json.loads(match.group(1))
        else:
            logging.error("Can't find video info.")
            return episodes
        seasons = []
        if "series" not in janson["initialState"]:
            return [self.url]
        for season in janson["initialState"]["series"]["seasonInfo"]:
            seasons.append(season["id"])
        for season in janson["initialState"]["seasons"]:
            if season["id"] in seasons:
                for episode in season["episodes"]:
                    if episode["availability"]["status"] == "available":
                        episodes.append(urljoin("https://tv.nrk.no/", episode["playerPath"]))
            elif options.get("include_clips") and season["id"] == "ekstramateriale":
                for episode in season["episodes"]:
                    if episode["availability"]["status"] == "available":
                        episodes.append(urljoin("https://tv.nrk.no/", episode["playerPath"]))

        return episodes

    def outputfilename(self):
        self.output["title"] = self.janson["initialState"]["series"]["title"]
        self.output["id"] = self.video_id.lower()
        for season in self.janson["initialState"]["seasons"]:
            for episode in season["episodes"]:
                if self.video_id == episode["prfId"]:
                    if episode["season"]["id"] and episode["season"]["id"].isnumeric():
                        self.output["season"] = episode["season"]["id"]
                    if "sequenceNumber" in episode:
                        self.output["episode"] = episode["sequenceNumber"]
                    self.output["episodename"] = episode["title"]
