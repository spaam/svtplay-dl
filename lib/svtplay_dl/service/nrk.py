# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Nrk(Service, OpenGraphThumbMixin):
    supported_domains = ['nrk.no', 'tv.nrk.no', 'p3.no', 'tv.nrksuper.no']

    def get(self):
        if self.exclude():
            yield ServiceError("Excluding video")
            return

        # First, fint the video ID from the html document
        match = re.search("<meta name=\"programid\".*?content=\"([^\"]*)\"", self.get_urldata())
        if match:
            video_id = match.group(1)
        else:
            yield ServiceError("Can't find video id.")
            return

        # Get media element details
        dataurl = "http://v8.psapi.nrk.no/mediaelement/%s" % (video_id)
        data = self.http.request("get", dataurl).text
        data = json.loads(data)
        manifest_url = data["mediaUrl"]
        self.options.live = data["isLive"]
        if manifest_url is None:
            yield ServiceError(data["messageType"])
            return
        # Check if subtitles are available
        if data["subtitlesUrlPath"]:
            yield subtitle(copy.copy(self.options), "tt", data["subtitlesUrlPath"])

        hlsurl = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        data = self.http.request("get", hlsurl)
        if data.status_code == 403:
            yield ServiceError("Can't fetch the video because of geoblocking")
            return
        streams = hlsparse(self.options, data, hlsurl)
        for n in list(streams.keys()):
            yield streams[n]

        streams = hdsparse(copy.copy(self.options), self.http.request("get", manifest_url, params={"hdcore": "3.7.0"}),
                           manifest_url)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]
