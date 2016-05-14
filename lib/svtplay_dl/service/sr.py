# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import json
import re
import copy

from svtplay_dl.utils.urllib import quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ['sverigesradio.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'href="(/sida/[\.\/=a-z0-9&;\?]+play(?:audio|episode)=\d+)"', data)
        if not match:
            yield ServiceError("Can't find audio info")
            return
        path = quote_plus(match.group(1))
        dataurl = "http://sverigesradio.se/sida/ajax/getplayerinfo?url=%s&isios=false&playertype=html5" % path
        data = self.http.request("get", dataurl).text
        playerinfo = json.loads(data)["playerInfo"]
        for i in playerinfo["AudioSources"]:
            url = i["Url"]
            if not url.startswith('http'):
                url = 'http:%s' % url
            yield HTTP(copy.copy(self.options), url, i["Quality"]/1000)


