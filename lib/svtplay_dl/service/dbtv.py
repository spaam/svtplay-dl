from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Dbtv(Service, OpenGraphThumbMixin):
    supported_domains = ['dbtv.no']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        parse = urlparse(self.url)
        vidoid = parse.path[parse.path.rfind("/") + 1:]
        match = re.search(r'JSONdata = ({.*});', data)
        if not match:
            yield ServiceError("Cant find json data")
            return
        janson = json.loads(match.group(1))
        playlist = janson["playlist"]
        for i in playlist:
            if i["brightcoveId"] == int(vidoid):
                if i["HLSURL"]:
                    streams = hlsparse(self.options, self.http.request("get", i["HLSURL"]), i["HLSURL"])
                    for n in list(streams.keys()):
                        yield streams[n]
                for n in i["renditions"]:
                    if n["container"] == "MP4":
                        yield HTTP(copy.copy(self.options), n["URL"], int(n["rate"]) / 1000)
