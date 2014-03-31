# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import sys

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.log import log

class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ['dn.se']

    def get(self, options):
        data = self.get_urldata()
        ajax_auth = re.search(r"picsearch_ajax_auth = '(\w+)'", data)
        if not ajax_auth:
            log.error("Cant find token for video")
            sys.exit(2)
        mediaid = re.search(r"mediaId = '(\w+)';", data)
        if not mediaid:
            log.error("Cant find media id")
            sys.exit(2)
        jsondata = get_http_data("http://csp.picsearch.com/rest?jsonp=&eventParam=1&auth=%s&method=embed&mediaid=%s" % (ajax_auth.group(1), mediaid.group(1)))
        jsondata = json.loads(jsondata)
        files = jsondata["media"]["playerconfig"]["playlist"][1]["bitrates"]
        server = jsondata["media"]["playerconfig"]["plugins"]["bwcheck"]["netConnectionUrl"]

        streams = {}
        for i in files:
            streams[int(i["height"])] = i["url"]

        path = select_quality(options, streams)

        options.other = "-y '%s'" % path
        download_rtmp(options, server)