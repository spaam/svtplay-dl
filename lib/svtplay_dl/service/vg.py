import copy
import json
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Vg(Service, OpenGraphThumbMixin):
    supported_domains = ["vg.no", "vgtv.no"]

    def get(self):
        data = self.get_urldata()
        match = re.search(r'data-videoid="([^"]+)"', data)
        if not match:
            parse = urlparse(self.url)
            match = re.search(r"video/(\d+)/", parse.fragment)
            if not match:
                yield ServiceError(f"Can't find video file for: {self.url}")
                return
        videoid = match.group(1)
        data = self.http.request("get", f"http://svp.vg.no/svp/api/v1/vgtv/assets/{videoid}?appName=vgtv-website").text
        jsondata = json.loads(data)
        self.output["title"] = jsondata["title"]

        if "hds" in jsondata["streamUrls"]:
            streams = hdsparse(
                self.config,
                self.http.request("get", jsondata["streamUrls"]["hds"], params={"hdcore": "3.7.0"}),
                jsondata["streamUrls"]["hds"],
                output=self.output,
            )
            for n in list(streams.keys()):
                yield streams[n]
        if "hls" in jsondata["streamUrls"]:
            streams = hlsparse(
                self.config,
                self.http.request("get", jsondata["streamUrls"]["hls"]),
                jsondata["streamUrls"]["hls"],
                output=self.output,
            )
            for n in list(streams.keys()):
                yield streams[n]
        if "mp4" in jsondata["streamUrls"]:
            yield HTTP(copy.copy(self.config), jsondata["streamUrls"]["mp4"], output=self.output)
