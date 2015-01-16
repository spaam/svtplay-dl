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
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.http import HTTP

class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ['sverigesradio.se']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return

        if self.exclude(options):
            return

        match = re.search(r'href="(/sida/[\.\/=a-z0-9&;\?]+\d+)" aria-label', data)
        if not match:
            log.error("Can't find audio info")
            return
        path = quote_plus(match.group(1))
        dataurl = "http://sverigesradio.se/sida/ajax/getplayerinfo?url=%s&isios=false&playertype=html5" % path
        error, data = get_http_data(dataurl)
        if error:
            log.error("Cant get stream info")
            return
        playerinfo = json.loads(data)["playerInfo"]
        for i in playerinfo["AudioSources"]:
            url = i["Url"]
            if not url.startswith('http'):
                url = 'http:%s' % url
            yield HTTP(copy.copy(options), url, i["Quality"]/1000)


