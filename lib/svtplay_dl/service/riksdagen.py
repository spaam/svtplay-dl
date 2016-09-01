from __future__ import absolute_import
import re
from svtplay_dl.fetcher.hls import hlsparse


from svtplay_dl.service import Service, OpenGraphThumbMixin

from svtplay_dl.error import ServiceError


class Riksdagen(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.riksdagen.se"]

    def get(self):
        match = re.search("_([A-Z0-9]+)$", self.url)
        if not match:
            yield ServiceError("Cant find video id.")
            return

        vid = match.group(1)
        res = self.http.get("http://www.riksdagen.se/api/videostream/get/%s" % vid)
        data = res.json()

        try:
            janson = data["videodata"][0]["streams"]["files"]
        except TypeError:
            yield ServiceError("Cant find video.")
            return

        for i in janson:
            if i["mimetype"] == "application/x-mpegurl":
                data2 = self.http.get(i["url"]).json()
                streams = hlsparse(self.options, self.http.request("get", data2["url"]), data2["url"])
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
