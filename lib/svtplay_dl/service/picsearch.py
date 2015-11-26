# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.error import ServiceError


class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ['dn.se', 'mobil.dn.se', 'di.se']

    def get(self, options):
        data = self.get_urldata()

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        ajax_auth = re.search(r"picsearch_ajax_auth = '(\w+)'", data)
        if not ajax_auth:
            ajax_auth = re.search(r'screen9-ajax-auth="([^"]+)"', data)
            if not ajax_auth:
                yield ServiceError("Cant find token for video")
                return
        mediaid = re.search(r"mediaId = '([^']+)';", self.get_urldata())
        if not mediaid:
            mediaid = re.search(r'media-id="([^"]+)"', self.get_urldata())
            if not mediaid:
                mediaid = re.search(r'screen9-mid="([^"]+)"', self.get_urldata())
                if not mediaid:
                    yield ServiceError("Cant find media id")
                    return
        jsondata = self.http.request("get", "http://csp.picsearch.com/rest?jsonp=&eventParam=1&auth=%s&method=embed&mediaid=%s" % (ajax_auth.group(1), mediaid.group(1))).text
        jsondata = json.loads(jsondata)
        if "playerconfig" not in jsondata["media"]:
            yield ServiceError(jsondata["error"])
            return
        if "live" in jsondata["media"]["playerconfig"]["clip"]:
            options.live = jsondata["media"]["playerconfig"]["clip"]
        playlist = jsondata["media"]["playerconfig"]["playlist"][1]
        if "bitrates" in playlist:
            files = playlist["bitrates"]
            server = jsondata["media"]["playerconfig"]["plugins"]["bwcheck"]["netConnectionUrl"]

            for i in files:
                options.other = "-y '%s'" % i["url"]
                yield RTMP(copy.copy(options), server, i["height"])
        if "provider" in playlist:
            if playlist["provider"] != "rtmp":
                if "live" in playlist:
                    options.live = playlist["live"]
                if playlist["url"].endswith(".f4m"):
                    streams = hdsparse(options, self.http.request("get", playlist["url"], params={"hdcore": "3.7.0"}), playlist["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
