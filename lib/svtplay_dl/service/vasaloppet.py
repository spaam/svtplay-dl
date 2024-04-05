# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Vasaloppet(Service, OpenGraphThumbMixin):
    supported_domains = ["vasaloppet.tv"]

    def get(self):
        match = re.search(r'iframe src="(https://vlplayer.rack[^"]+)" width', self.get_urldata())
        if not match:
            yield ServiceError("Can't find video")
            return

        parse = urlparse(match.group(1))
        status_url = f"http://{parse.netloc}{parse.path}/status"
        res = self.http.get(status_url)
        janson = res.json()
        hls = janson["vods"][0]["hls"]
        yield from hlsparse(self.config, self.http.request("get", hls), hls, output=self.output)
