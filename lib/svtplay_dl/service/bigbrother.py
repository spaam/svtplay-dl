# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse, HLS

class Bigbrother(Service, OpenGraphThumbMixin):
    supported_domains = ["bigbrother.se"]

    def get(self, options):
        match = re.search(r'id="(bcPl[^"]+)"', self.get_urldata())
        if not match:
            log.error("Can't find flash id.")
            sys.exit(2)
        flashid = match.group(1)

        match = re.search(r'playerID" value="([^"]+)"', self.get_urldata())
        if not match:
            log.error("Can't find playerID")
            sys.exit(2)
        playerid = match.group(1)

        match = re.search(r'playerKey" value="([^"]+)"', self.get_urldata())
        if not match:
            log.error("Can't find playerKey")
            sys.exit(2)
        playerkey = match.group(1)

        match = re.search(r'videoPlayer" value="([^"]+)"', self.get_urldata())
        if not match:
            log.error("Can't find videoPlayer info")
            sys.exit(2)
        videoplayer = match.group(1)

        dataurl = "http://c.brightcove.com/services/viewer/htmlFederated?flashID=%s&playerID=%s&playerKey=%s&isVid=true&isUI=true&dynamicStreaming=true&@videoPlayer=%s" % (flashid, playerid, playerkey, videoplayer)
        data = get_http_data(dataurl)
        match = re.search(r'experienceJSON = ({.*});', data)
        if not match:
            log.error("Can't find json data")
            sys.exit(2)
        jsondata = json.loads(match.group(1))
        renditions = jsondata["data"]["programmedContent"]["videoPlayer"]["mediaDTO"]["renditions"]
        for i in renditions:
            if i["defaultURL"].endswith("f4m"):
                manifest = "%s?hdcore=3.3.0" % i["defaultURL"]
                streams = hdsparse(copy.copy(options), manifest)
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]

            if i["defaultURL"].endswith("m3u8"):
                streams = hlsparse(i["defaultURL"])
                for n in list(streams.keys()):
                    yield HLS(copy.copy(options), streams[n], n)
