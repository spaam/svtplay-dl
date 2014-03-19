# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import json
import re

from svtplay_dl.utils.urllib import quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.log import log
from svtplay_dl.fetcher.http import download_http

class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ['sverigesradio.se']

    def get(self, options):
        match = re.search(r'href="(/sida/[\.\/=a-z0-9&;\?]+\d+)" aria-label', self.get_urldata())
        if not match:
            log.error("Can't find audio info")
            sys.exit(2)
        path = quote_plus(match.group(1))
        dataurl = "http://sverigesradio.se/sida/ajax/getplayerinfo?url=%s&isios=false&playertype=html5" % path
        data = get_http_data(dataurl)
        playerinfo = json.loads(data)["playerInfo"]
        streams = {}
        for i in playerinfo["AudioSources"]:
            url = i["Url"]
            if not url.startswith('http'):
                i = 'http:%s' % url
            streams[int(i["Quality"])] = url

        test = select_quality(options, streams)
        download_http(options, test)

