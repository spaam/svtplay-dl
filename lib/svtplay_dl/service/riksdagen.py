import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Riksdagen(Service, OpenGraphThumbMixin):
    supported_domains_re = ["riksdagen.se", "www.riksdagen.se"]

    def get(self):

        match = re.search(r"application\/json\">({.+})<\/script>", self.get_urldata())
        if not match:
            yield ServiceError("Cant find the video.")
            return

        janson = json.loads(match.group(1))
        url = janson["props"]["pageProps"]["contentApiData"]["video"]["url"]
        yield from hlsparse(self.config, self.http.request("get", url), url, output=self.output)
