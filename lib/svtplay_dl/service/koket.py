# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Koket(Service, OpenGraphThumbMixin):
    supported_domains = ["koket.se"]

    def get(self):
        urlp = urlparse(self.url)
        if urlp.path.startswith("/kurser"):
            res = self.http.post(
                "https://www.koket.se/konto/authentication/login",
                json={"username": self.config.get("username"), "password": self.config.get("password")},
            )
            if "errorMessage" in res.json():
                yield ServiceError("Wrong username or password")
                return
        data = self.http.get(self.url)
        match = re.search(r'({"@.*})', data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        janson = json.loads(f"[{match.group(1)}]")
        for i in janson:
            if "video" in i:
                self.output["title"] = i["video"]["name"]
                break

        match = re.search(r"dataLayer = (\[.*\]);<", data)
        if not match:
            yield ServiceError("Can't find video id")
            return

        janson = json.loads(match.group(1))
        self.output["id"] = janson[0]["video"]

        url = f"https://playback-api.b17g.net/media/{self.output['id']}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine"

        videoDataRes = self.http.get(url)
        if videoDataRes.json()["playbackItem"]["type"] == "hls":
            yield from hlsparse(
                self.config,
                self.http.get(videoDataRes.json()["playbackItem"]["manifestUrl"]),
                videoDataRes.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
