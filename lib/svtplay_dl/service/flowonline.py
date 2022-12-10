# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe


class Flowonline(Service, OpenGraphThumbMixin):
    supported_domains_re = [r"^([a-z]{1,4}\.|www\.)?flowonline\.tv$"]

    def get(self):
        match = re.search('iframe src="(/embed/[^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find video")
            return
        parse = urlparse(self.url)

        url = f"{parse.scheme}://{parse.netloc}{match.group(1)}"

        data = self.http.get(url)

        match = re.search('src="([^"]+vtt)"', data.text)
        if match:
            yield from subtitle_probe(copy.copy(self.config), match.group(1))

        match = re.search('source src="([^"]+)" type="application/x-mpegURL"', data.text)
        if not match:
            yield ServiceError("Cant find video file")
            return

        yield from hlsparse(self.config, self.http.request("get", match.group(1)), match.group(1), output=self.output)
