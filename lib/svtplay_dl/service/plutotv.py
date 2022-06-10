import datetime
import re
import uuid
from typing import Union
from urllib.parse import ParseResult
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Plutotv(Service, OpenGraphThumbMixin):
    supported_domains = ["pluto.tv"]

    def get(self):
        data = self.get_urldata()
        parse = urlparse(self.url)

        match = re.search("episode/([^/]+)$", parse.path)
        if not match:
            match = re.search("movies/([^/]+)$", parse.path)
            if not match:
                yield ServiceError("Can't find what video it is")
                return
        episodename = match.group(1)
        janson = self._janson(data, parse)

        mediaserver = janson["servers"]["stitcher"]
        stitcherParams = janson["stitcherParams"]
        sessionToken = janson["sessionToken"]
        HLSplaylist = None
        for show in janson["VOD"]:
            if "seasons" in show:
                self.output["title"] = show["name"]
                for season in show["seasons"]:
                    for episode in season["episodes"]:
                        if episode["slug"] == episodename:
                            match = re.search(r" (\d+)$", episode["name"])
                            if match:
                                self.output["season"] = int(match.group(1)) // 100
                                self.output["episode"] = int(match.group(1)) % 100
                            for stich in episode["stitched"]["paths"]:
                                if stich["type"] == "hls":
                                    HLSplaylist = stich["path"]

            else:
                if show["slug"] == episodename:
                    self.output["title"] == show["name"]
                    for stich in show["stitched"]["paths"]:
                        if stich["type"] == "hls":
                            HLSplaylist = stich["path"]

        if not HLSplaylist:
            yield ServiceError("Can't find video info")
            return
        playlistURL = f"{mediaserver}{HLSplaylist}?{stitcherParams}"
        yield from hlsparse(
            self.config,
            self.http.request("get", playlistURL, headers={"Authorization": f"Bearer {sessionToken}"}),
            playlistURL,
            self.output,
            filter=True,
        )

    def find_all_episodes(self, options):
        episodes = []
        data = self.get_urldata()
        parse = urlparse(self.url)
        janson = self._janson(data, parse)

        match = re.search(r"^/([^\/]+)/", parse.path)
        language = match.group(1)

        for show in janson["VOD"]:
            showname = show["slug"]
            if "seasons" in show:
                for season in show["seasons"]:
                    seasonnr = season["number"]
                    for episode in season["episodes"]:
                        episodes.append(f"https://pluto.tv/{language}/on-demand/series/{showname}/{seasonnr}/episode/{episode['slug']}")
        return episodes

    def _janson(self, data: str, parse: ParseResult) -> Union[dict, None]:
        match = re.search(r"on-demand/\w+/([^/]+)", parse.path)
        if not match:
            return None

        series = match.group(1)

        match = re.search('appVersion" content="([^"]+)"', data)
        if not match:
            return None

        appversion = match.group(1)
        res = self.http.request(
            "get",
            f"https://boot.pluto.tv/v4/start?appName=web&appVersion={appversion}&deviceVersion=100.0.0&deviceModel=web&deviceMake=firefox&deviceType=web&clientID={uuid.uuid1()}&clientModelNumber=1.0.0&episodeSlugs={series}&serverSideAds=true&constraints=&drmCapabilities=widevine%3AL3&clientTime={datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}",
        )
        return res.json()
