# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
from urllib.parse import urlparse

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError
from svtplay_dl.subtitle import subtitle


class Flowonline(Service, OpenGraphThumbMixin):
    supported_domains_re = [
        r'^([a-z]{1,4}\.|www\.)?flowonline\.tv$',
    ]

    def get(self):
        match = re.search('iframe src="(/embed/[^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find video")
            return
        parse = urlparse(self.url)

        url = "{0}://{1}{2}".format(parse.scheme, parse.netloc, match.group(1))

        data = self.http.get(url)

        match = re.search('src="([^"]+vtt)"', data.text)
        if match:
            yield subtitle(copy.copy(self.config), "wrst", match.group(1))

        match = re.search('source src="([^"]+)" type="application/x-mpegURL"', data.text)
        if not match:
            yield ServiceError("Cant find video file")
            return

        streams = hlsparse(self.config, self.http.request("get", match.group(1)), match.group(1), output=self.output)
        for n in list(streams.keys()):
            yield streams[n]
