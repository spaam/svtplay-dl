import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Pokemon(Service, OpenGraphThumbMixin):
    supported_domains = ["watch.pokemon.com"]

    def get(self):
        parse = urlparse(self.url)
        if parse.fragment == "":
            yield ServiceError("need the whole url")
            return

        match = re.search(r"id=([a-f0-9]+)\&", parse.fragment)
        if not match:
            yield ServiceError("Cant find the ID in the url")
            return

        match2 = re.search(r'region: "(\w+)"', self.get_urldata())
        if not match2:
            yield ServiceError("Can't find region data")
            return

        res = self.http.get(f"https://www.pokemon.com/api/pokemontv/v2/channels/{match2.group(1)}/")
        janson = res.json()
        stream = None
        for i in janson:
            for n in i["media"]:
                if n["id"] == match.group(1):
                    stream = n
                    break

        if stream is None:
            yield ServiceError("Can't find video")
            return

        self.output["title"] = "pokemon"
        self.output["season"] = stream["season"]
        self.output["episode"] = stream["episode"]
        self.output["episodename"] = stream["title"]

        yield from hlsparse(self.config, self.http.request("get", stream["stream_url"]), stream["stream_url"], output=self.output)
