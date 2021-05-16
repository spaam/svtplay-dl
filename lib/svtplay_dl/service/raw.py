import os
import re

from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Raw(Service):
    def get(self):
        filename = os.path.basename(self.url[: self.url.rfind("/")])
        self.output["title"] = filename

        if re.search(".m3u8", self.url):
            yield from hlsparse(self.config, self.http.request("get", self.url), self.url, output=self.output)

        if re.search(".mpd", self.url):
            yield from dashparse(self.config, self.http.request("get", self.url), self.url, output=self.output)
