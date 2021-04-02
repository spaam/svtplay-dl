# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


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

        # Get media element details
        match = re.search('psapi-base-url="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find apiurl.")
            return
        dataurl = "{}/mediaelement/{}".format(match.group(1), video_id)
        data = self.http.request("get", dataurl).text
        data = json.loads(data)
        manifest_url = data["mediaUrl"]
        self.config.set("live", data["isLive"])
        if manifest_url is None:
            yield ServiceError(data["messageType"])
            return
        # Check if subtitles are available
        if data["subtitlesUrlPath"]:
            yield subtitle(copy.copy(self.config), "tt", data["subtitlesUrlPath"], output=self.output)

        hlsurl = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        data = self.http.request("get", hlsurl)
        if data.status_code == 403:
            yield ServiceError("Can't fetch the video because of geoblocking")
            return
        streams = hlsparse(self.config, data, hlsurl, output=self.output)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]

        else:
            streams = hdsparse(
                copy.copy(self.config),
                self.http.request("get", manifest_url, params={"hdcore": "3.7.0"}),
                manifest_url,
                output=self.output,
            )
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
