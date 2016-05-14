# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json

from svtplay_dl.utils.urllib import unquote_plus
from svtplay_dl.service import Service
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils import decode_html_entities

class Lemonwhale(Service):
    # lemonwhale.com is just bogus for generic
    supported_domains = ['svd.se', 'vk.se', 'lemonwhale.com']

    def get(self):
        vid = None
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'video url-([^"]+)', data)
        if not match:
            match = re.search(r'embed.jsp\?([^"]+)"', self.get_urldata())
            if not match:
                yield ServiceError("Can't find video id")
                return
            vid = match.group(1)
        if not vid:
            path = unquote_plus(match.group(1))
            data = self.http.request("get", "http://www.svd.se%s" % path).content
            match = re.search(r'embed.jsp\?([^"]+)', data)
            if not match:
                yield ServiceError("Can't find video id")
                return
            vid = match.group(1)

        url = "http://ljsp.lwcdn.com/web/public/item.json?type=video&%s" % decode_html_entities(vid)
        data = self.http.request("get", url).text
        jdata = json.loads(data)
        videos = jdata["videos"][0]["media"]["streams"]
        for i in videos:
            if i["name"] == "auto":
                hls = "%s%s" % (jdata["videos"][0]["media"]["base"], i["url"])
        streams = hlsparse(self.options, self.http.request("get", hls), hls)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]
