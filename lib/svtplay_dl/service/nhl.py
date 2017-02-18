from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class NHL(Service, OpenGraphThumbMixin):
    supported_domains = ['nhl.com']

    def get(self):
        if self.exclude():
            yield ServiceError("Excluding video")
            return
        match = re.search("var initialMedia\s+= ({[^;]+);", self.get_urldata())
        if not match:
            yield ServiceError("Cant find any media on that page")
            return
        janson = json.loads(match.group(1))
        if "playbacks" in janson["metaData"]:
            for i in janson["metaData"]["playbacks"]:
                if "CLOUD" in i["name"]:
                    streams = hlsparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
        else:
            yield ServiceError("Can't find any video metadata")
            return
