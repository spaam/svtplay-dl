import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Efn(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.efn.se"]

    def get(self):
        match = re.search('data-hls="([^"]+)"', self.get_urldata())
        if not match:
            yield ServiceError("Can't find video info")
            return

        yield from hlsparse(self.config, self.http.request("get", match.group(1)), match.group(1), output=self.output)
