from __future__ import absolute_import
import re
import json
import copy
import os

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.utils import get_http_data, filenamify
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.log import log

class Vg(Service, OpenGraphThumbMixin):
    supported_domains = ['vg.no', 'vgtv.no']

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return
        match = re.search(r'data-videoid="([^"]+)"', data)
        if not match:
            parse = urlparse(self.url)
            match = re.search(r'video/(\d+)/', parse.fragment)
            if not match:
                log.error("Can't find video file for: %s", self.url)
                return
        videoid = match.group(1)
        error, data = get_http_data("http://svp.vg.no/svp/api/v1/vgtv/assets/%s?appName=vgtv-website" % videoid)
        if error:
            log.error("Cant get video info")
            return
        jsondata = json.loads(data)

        if options.output_auto:
            directory = os.path.dirname(options.output)
            title = "%s" % jsondata["title"]
            title = filenamify(title)
            if len(directory):
                options.output = "%s/%s" % (directory, title)
            else:
                options.output = title

        if self.exclude(options):
            return

        if "hds" in jsondata["streamUrls"]:
            streams = hdsparse(copy.copy(options), jsondata["streamUrls"]["hds"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        if "hls" in jsondata["streamUrls"]:
            streams = hlsparse(jsondata["streamUrls"]["hls"])
            for n in list(streams.keys()):
                yield HLS(copy.copy(options), streams[n], n)
        if "mp4" in jsondata["streamUrls"]:
            yield HTTP(copy.copy(options), jsondata["streamUrls"]["mp4"])