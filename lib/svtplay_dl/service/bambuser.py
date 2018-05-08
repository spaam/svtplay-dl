# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.http import HTTP


class Bambuser(Service, OpenGraphThumbMixin):
    supported_domains = ["bambuser.com"]

    def get(self):
        match = re.search(r"v/(\d+)", self.url)
        if not match:
            yield ServiceError("Can't find video id in url")
            return

        json_url = "http://player-c.api.bambuser.com/getVideo.json?api_key=005f64509e19a868399060af746a00aa&vid={0}".format(match.group(1))
        data = self.http.request("get", json_url).text

        info = json.loads(data)["result"]
        video = info["url"]
        if video[:4] == "rtmp":
            playpath = info["id"][len(info["id"]) - 36:]
            other = "-y {0}".format(playpath)
            if info["type"] == "live":
                self.config.set("live", True)
            yield RTMP(copy.copy(self.config), video, "0", other=other)
        else:
            yield HTTP(copy.copy(self.config), video, "0")
