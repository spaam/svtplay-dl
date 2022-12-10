# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe


class Nrk(Service, OpenGraphThumbMixin):
    supported_domains = ["nrk.no", "tv.nrk.no", "p3.no", "tv.nrksuper.no"]

    def get(self):
        # First, fint the video ID from the html document
        match = re.search('program-id" content="([^"]+)"', self.get_urldata())
        if match:
            video_id = match.group(1)
        else:
            yield ServiceError("Can't find video id.")
            return

        dataurl = f"https://psapi.nrk.no/playback/manifest/program/{video_id}?eea-portability=true"
        janson = self.http.request("get", dataurl).json()

        if janson["playable"]:
            if janson["playable"]["assets"][0]["format"] == "HLS":
                yield from hlsparse(
                    self.config,
                    self.http.request("get", janson["playable"]["assets"][0]["url"]),
                    janson["playable"]["assets"][0]["url"],
                    output=self.output,
                )

            # Check if subtitles are available
            for sub in janson["playable"]["subtitles"]:
                if sub["defaultOn"]:
                    yield from subtitle_probe(copy.copy(self.config), sub["webVtt"], output=self.output)
