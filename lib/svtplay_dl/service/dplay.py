# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import json
import time

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils.urllib import quote
from svtplay_dl.error import ServiceError


class Dplay(Service):
    supported_domains = ['dplay.se']

    def get(self, options):
        data = self.get_urldata()

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        match = re.search("<link rel='shortlink' href='http://www.dplay.se/\?p=(\d+)", data)
        if not match:
            yield ServiceError("Can't find video id")
            return

        data = self.http.request("get", "http://geo.dplay.se/geo.js").text
        dataj = json.loads(data)
        geo = dataj["countryCode"]
        timestamp = (int(time.time())+3600)*1000
        cookie = {"dsc-geo": quote('{"countryCode":"%s","expiry":%s}' % (geo, timestamp))}
        data = self.http.request("get", "https://secure.dplay.se/secure/api/v2/user/authorization/stream/%s?stream_type=hds" % match.group(1), cookies=cookie)
        dataj = json.loads(data.text)
        if "hds" in dataj:
            streams = hdsparse(copy.copy(options), self.http.request("get", dataj["hds"], params={"hdcore": "3.8.0"}), dataj["hds"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        data = self.http.request("get", "https://secure.dplay.se/secure/api/v2/user/authorization/stream/%s?stream_type=hls" % match.group(1), cookies=cookie)
        dataj = json.loads(data.text)
        if "hls" in dataj:
            streams = hlsparse(options, self.http.request("get", dataj["hls"]), dataj["hls"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
