from __future__ import absolute_import
import re
import sys
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.log import log

class Dbtv(Service, OpenGraphThumbMixin):
    supported_domains = ['dbtv.no']

    def get(self, options):
        data = self.get_urldata()
        parse = urlparse(self.url)
        vidoid = parse.path[parse.path.rfind("/")+1:]
        match = re.search(r'JSONdata = ({.*});', data)
        if not match:
            log.error("Cant find json data")
            sys.exit(2)
        janson = json.loads(match.group(1))
        playlist = janson["playlist"]
        for i in playlist:
            if i["brightcoveId"] == vidoid:
                if i["HLSURL"]:
                    streams = hlsparse(i["HLSURL"])
                    for n in list(streams.keys()):
                        yield HLS(copy.copy(options), streams[n], n)
                for n in i["renditions"]:
                    if n["container"] == "MP4":
                        yield HTTP(copy.copy(options), n["URL"], int(n["rate"])/1000)


