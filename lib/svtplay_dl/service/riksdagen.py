import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Riksdagen(Service, OpenGraphThumbMixin):
    supported_domains_re = ["riksdagen.se", "www.riksdagen.se"]

    def get(self):
        match = re.search("_([a-zA-Z0-9]+)$", self.url)
        if not match:
            yield ServiceError("Cant find video id.")
            return

        vid = match.group(1)
        res = self.http.get(f"http://www.riksdagen.se/api/videostream/get/{vid}")
        data = res.json()

        try:
            janson = data["videodata"][0]["streams"]["files"]
        except TypeError:
            yield ServiceError("Cant find video.")
            return

        for i in janson:
            for n in i["bandwidth"]:
                yield from hlsparse(self.config, self.http.request("get", n["url"]), n["url"], output=self.output)
