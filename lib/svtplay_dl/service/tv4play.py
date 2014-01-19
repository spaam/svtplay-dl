# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse, parse_qs
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, select_quality, subtitle_smi, is_py2_old
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hds import download_hds

class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4play.se', 'tv4.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        parse = urlparse(self.url)
        if "tv4play.se" in self.url:
            try:
                vid = parse_qs(parse[4])["video_id"][0]
            except KeyError:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            match = re.search(r"-(\d+)$", self.url)
            if match:
                vid = match.group(1)
            else:
                data = get_http_data(self.url)
                match = re.search(r"\"vid\":\"(\d+)\",", data)
                if match:
                    vid = match.group(1)
                else:
                    log.error("Can't find video file")
                    sys.exit(2)

        url = "http://premium.tv4play.se/api/web/asset/%s/play" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if is_py2_old:
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            if xml.find("live").text != "false":
                options.live = True

        streams = {}

        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                stream = {}
                stream["uri"] = i.find("base").text
                stream["path"] = i.find("url").text
                streams[int(i.find("bitrate").text)] = stream
            elif i.find("mediaFormat").text == "smi":
                self.subtitle = i.find("url").text

        if len(streams) == 0:
            log.error("Can't find any streams")
            sys.exit(2)
        elif len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        ## This is how we construct an swf uri, if we'll ever need one
        swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
        options.other = "-W %s -y %s" % (swf, test["path"])

        if test["uri"][0:4] == "rtmp":
            download_rtmp(options, test["uri"])
        elif test["uri"][len(test["uri"])-3:len(test["uri"])] == "f4m":
            match = re.search(r"\/se\/secure\/", test["uri"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["path"]
            download_hds(options, manifest)


    def get_subtitle(self, options):
        if self.subtitle:
            data = get_http_data(self.subtitle)
            subtitle_smi(options, data)
