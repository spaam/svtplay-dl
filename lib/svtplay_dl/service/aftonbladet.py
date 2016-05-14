# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.utils import decode_html_entities
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse


class Aftonbladet(Service):
    supported_domains = ['tv.aftonbladet.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search('data-aptomaId="([-0-9a-z]+)"', data)
        if not match:
            match = re.search('data-player-config="([^"]+)"', data)
            if not match:
                yield ServiceError("Can't find video info")
                return
            janson = json.loads(decode_html_entities(match.group(1)))
            videoId = janson["videoId"]
        else:
            videoId = match.group(1)
            match = re.search(r'data-isLive="(\w+)"', data)
            if not match:
                yield ServiceError("Can't find live info")
                return
            if match.group(1) == "true":
                self.options.live = True

        if not self.options.live:
            dataurl = "http://aftonbladet-play-metadata.cdn.drvideo.aptoma.no/video/%s.json" % videoId
            data = self.http.request("get", dataurl).text
            data = json.loads(data)
            videoId = data["videoId"]

        streamsurl = "http://aftonbladet-play-static-ext.cdn.drvideo.aptoma.no/actions/video/?id=%s&formats&callback=" % videoId
        data = self.http.request("get", streamsurl).text
        streams = json.loads(data)
        hlsstreams = streams["formats"]["hls"]
        if "level3" in hlsstreams.keys():
            hls = hlsstreams["level3"]
        else:
            hls = hlsstreams["akamai"]
        if "csmil" in hls.keys():
            hls = hls["csmil"][0]
        else:
            hls = hls["m3u8"][0]
        address = hls["address"]
        path = hls["path"]

        for i in hls["files"]:
            if "filename" in i.keys():
                plist = "http://%s/%s/%s/master.m3u8" % (address, path, i["filename"])
            else:
                plist = "http://%s/%s/%s" % (address, path, hls["filename"])

            streams = hlsparse(self.options, self.http.request("get", plist), plist)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
