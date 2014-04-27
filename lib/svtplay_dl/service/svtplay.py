# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import json
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hds import HDS, hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.subtitle import subtitle_wsrt
from svtplay_dl.log import log

class Svtplay(Service, OpenGraphThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'beta.svtplay.se', 'svtflow.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        if re.findall("svt.se", self.url):
            match = re.search(r"data-json-href=\"(.*)\"", self.get_urldata())
            if match:
                filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
                url = "http://www.svt.se%s" % filename
            else:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            url = self.url

        pos = url.find("?")
        if pos < 0:
            dataurl = "%s?&output=json&format=json" % url
        else:
            dataurl = "%s&output=json&format=json" % url
        data = json.loads(get_http_data(dataurl))
        if "live" in data["video"]:
            options.live = data["video"]["live"]
        else:
            options.live = False

        if data["video"]["subtitleReferences"]:
            try:
                subtitle = data["video"]["subtitleReferences"][0]["url"]
            except KeyError:
                pass
            if len(subtitle) > 0:
                yield subtitle_wsrt(subtitle)

        for i in data["video"]["videoReferences"]:
            parse = urlparse(i["url"])

            if parse.path.find("m3u8") > 0:
                streams = hlsparse(i["url"])
                for n in list(streams.keys()):
                    yield HLS(options, streams[n], n)
            elif parse.path.find("f4m") > 0:
                match = re.search(r"\/se\/secure\/", i["url"])
                if not match:
                    manifest = "%s?hdcore=2.8.0&g=hejsan" % i["url"]
                    streams = hdsparse(options, manifest)
                    for n in list(streams.keys()):
                        yield streams[n]
            elif parse.scheme == "rtmp":
                embedurl = "%s?type=embed" % url
                data = get_http_data(embedurl)
                match = re.search(r"value=\"(/(public)?(statiskt)?/swf(/video)?/svtplayer-[0-9\.a-f]+swf)\"", data)
                swf = "http://www.svtplay.se%s" % match.group(1)
                options.other = "-W %s" % swf
                yield RTMP(options, i["url"], i["bitrate"])
            else:
                yield HTTP(options, i["url"], "0")

    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
        if match is None:
            log.error("Couldn't retrieve episode list")
            sys.exit(2)

        xml = ET.XML(get_http_data(match.group(1)))

        return sorted(x.text for x in xml.findall(".//item/link"))
