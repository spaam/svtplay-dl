# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP


class Bigbrother(Service, OpenGraphThumbMixin):
    supported_domains = ["bigbrother.se"]

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'id="(bcPl[^"]+)"', data)
        if not match:
            yield ServiceError("Can't find flash id.")
            return
        flashid = match.group(1)

        match = re.search(r'playerID" value="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Can't find playerID")
            return
        playerid = match.group(1)

        match = re.search(r'playerKey" value="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Can't find playerKey")
            return
        playerkey = match.group(1)

        match = re.search(r'videoPlayer" value="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Can't find videoPlayer info")
            return
        videoplayer = match.group(1)

        dataurl = "http://c.brightcove.com/services/viewer/htmlFederated?flashID=%s&playerID=%s&playerKey=%s&isVid=true&isUI=true&dynamicStreaming=true&@videoPlayer=%s" % (flashid, playerid, playerkey, videoplayer)
        data = self.http.request("get", dataurl).content
        match = re.search(r'experienceJSON = ({.*});', data)
        if not match:
            yield ServiceError("Can't find json data")
            return
        jsondata = json.loads(match.group(1))
        renditions = jsondata["data"]["programmedContent"]["videoPlayer"]["mediaDTO"]["renditions"]

        if jsondata["data"]["publisherType"] == "PREMIUM":
            yield ServiceError("Premium content")
            return

        for i in renditions:
            if i["defaultURL"].endswith("f4m"):
                streams = hdsparse(copy.copy(self.options), self.http.request("get", i["defaultURL"], params={"hdcore": "3.7.0"}), i["defaultURL"])
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]

            if i["defaultURL"].endswith("m3u8"):
                streams = hlsparse(self.options, self.http.request("get", i["defaultURL"]), i["defaultURL"])
                for n in list(streams.keys()):
                    yield streams[n]

            if i["defaultURL"].endswith("mp4"):
                yield HTTP(copy.copy(self.options), i["defaultURL"], i["encodingRate"]/1024)