from __future__ import absolute_import
import re
import json

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Viasatsport(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.viasatsport.se"]

    def get(self):
        match = re.search("__STATE__']=({.*});</script><script>window", self.get_urldata())
        if not match:
            yield ServiceError("Cant find video info")
            return

        dataj = json.loads(match.group(1))
        vid = dataj["dataSources"]["article"][0]["videos"][0]["data"]["mediaGuid"]

        url = "https://viasport.mtg-api.com/stream-links/viasport/web/se/clear-media-guids/%s/streams" % vid
        data = self.http.get(url)
        dataj = data.json()
        hls = dataj["embedded"]["prioritizedStreams"][0]["links"]["stream"]["href"]
        if re.search("/live/", hls):
            self.options.live = True
        streams = hlsparse(self.options, self.http.request("get", hls), hls)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]