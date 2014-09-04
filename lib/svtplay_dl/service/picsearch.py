# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import sys
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.log import log

class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ['dn.se', 'mobil.dn.se']

    def get(self, options):
        data = self.get_urldata()
        ajax_auth = re.search(r"picsearch_ajax_auth = '(\w+)'", data)
        if not ajax_auth:
            log.error("Cant find token for video")
            sys.exit(2)
        mediaid = re.search(r"mediaId = '([^']+)';", data)
        if not mediaid:
            mediaid = re.search(r'media-id="([^"]+)"', data)
            if not mediaid:
                log.error("Cant find media id")
                sys.exit(2)
        jsondata = get_http_data("http://csp.picsearch.com/rest?jsonp=&eventParam=1&auth=%s&method=embed&mediaid=%s" % (ajax_auth.group(1), mediaid.group(1)))
        jsondata = json.loads(jsondata)
        files = jsondata["media"]["playerconfig"]["playlist"][1]["bitrates"]
        server = jsondata["media"]["playerconfig"]["plugins"]["bwcheck"]["netConnectionUrl"]

        for i in files:
            options.other = "-y '%s'" % i["url"]
            yield RTMP(copy.copy(options), server, i["height"])
