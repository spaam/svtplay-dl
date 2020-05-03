import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Pokemon(Service, OpenGraphThumbMixin):
    supported_domains = ["pokemon.com"]

    def get(self):
        data = self.get_urldata()

        parse = urlparse(self.url)
        match = re.search(r"^/([a-z]{2})/", parse.path)
        if not match:
            yield ServiceError("Cant county code")
            return

        res = self.http.get("http://www.pokemon.com/api/pokemontv/channels?region={}".format(match.group(1)))
        janson = res.json()
        match = re.search('data-video-season="([0-9]+)"', data)
        season = match.group(1)
        match = re.search('data-video-episode="([0-9]+)"', data)
        episode = match.group(1)

        for i in janson:
            for n in i["media"]:
                if season == n["season"] and episode == n["episode"]:
                    stream = n["stream_url"]

        self.output["title"] = "pokemon"
        self.output["season"] = season
        self.output["episode"] = episode

        streams = hlsparse(self.config, self.http.request("get", stream), stream, output=self.output)
        for n in list(streams.keys()):
            yield streams[n]
