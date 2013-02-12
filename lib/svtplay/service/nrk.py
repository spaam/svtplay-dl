import re

from lib.svtplay.utils import get_http_data
from lib.svtplay.hds import download_hds
from lib.svtplay.hls import download_hls

class Nrk(object):
    def handle(self, url):
        return "nrk.no" in url

    def get(self, options, url):
        data = get_http_data(url)
        match = re.search(r'data-media="(.*manifest.f4m)"', data)
        manifest_url = match.group(1)
        if options.hls:
            manifest_url = manifest_url.replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
            download_hls(options, manifest_url)
        else:
            manifest_url = "%s?hdcore=2.8.0&g=hejsan" % manifest_url
            download_hds(options, manifest_url)

