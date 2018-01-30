# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils import decode_html_entities


class Lemonwhale(Service):
    # lemonwhale.com is just bogus for generic
    supported_domains = ['vk.se', 'lemonwhale.com']

    def get(self):
        if self.exclude():
            yield ServiceError("Excluding video")
            return

        vid = self.get_vid()
        if not vid:
            yield ServiceError("Can't find video id")
            return

        url = "http://ljsp.lwcdn.com/web/public/item.json?type=video&%s" % decode_html_entities(vid)
        data = self.http.request("get", url).text
        jdata = json.loads(data)
        if "videos" in jdata:
            streams = self.get_video(jdata)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]

        url = "http://ljsp.lwcdn.com/web/public/video.json?id={0}&delivery=hls".format(decode_html_entities(vid))
        data = self.http.request("get", url).text
        jdata = json.loads(data)
        if "videos" in jdata:
            streams = self.get_video(jdata)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]

    def get_vid(self):
        match = re.search(r'video url-([^"]+)', self.get_urldata())
        if match:
            return match.group(1)

        match = re.search(r'__INITIAL_STATE__ = ({.*})</script>', self.get_urldata())
        if match:
            janson = json.loads(match.group(1))
            vid = janson["content"]["current"]["data"]["templateData"]["pageData"]["video"]["id"]
            return vid

        match = re.search(r'embed.jsp\?([^"]+)"', self.get_urldata())
        if match:
            return match.group(1)
        return None

    def get_video(self, janson):
        videos = janson["videos"][0]["media"]["streams"]
        for i in videos:
            if i["name"] == "auto":
                hls = "{0}{1}".format(janson["videos"][0]["media"]["base"], i["url"])
        streams = hlsparse(self.options, self.http.request("get", hls), hls)
        return streams
