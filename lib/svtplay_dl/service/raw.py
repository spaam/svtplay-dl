import os
import re

from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Raw(Service):
    def get(self):
        filename = os.path.basename(self.url[: self.url.rfind("/")])
        self.output["title"] = filename

        streams = []
        if re.search(".f4m", self.url):
            self.output["ext"] = "flv"
            streams.append(hdsparse(self.config, self.http.request("get", self.url, params={"hdcore": "3.7.0"}), self.url, output=self.output))

        if re.search(".m3u8", self.url):
            streams.append(hlsparse(self.config, self.http.request("get", self.url), self.url, output=self.output))

        if re.search(".mpd", self.url):
            streams.append(dashparse(self.config, self.http.request("get", self.url), self.url, output=self.output))

        for stream in streams:
            if stream:
                for n in list(stream.keys()):
                    yield stream[n]
