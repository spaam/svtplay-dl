# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay.utils import get_http_data, select_quality
from svtplay.log import log
from svtplay.fetcher.rtmp import download_rtmp
from svtplay.fetcher.hds import download_hds

if sys.version_info > (3, 0):
    from urllib.parse import urlparse, parse_qs
else:
    from urlparse import urlparse, parse_qs

class Tv4play():
    def handle(self, url):
        return ("tv4play.se" in url) or ("tv4.se" in url)

    def get(self, options, url):
        parse = urlparse(url)
        if "tv4play.se" in url:
            try:
                vid = parse_qs(parse[4])["video_id"][0]
            except KeyError:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            match = re.search("-(\d+)$", url)
            if match:
                vid = match.group(1)
            else:
                data = get_http_data(url)
                match = re.search("\"vid\":\"(\d+)\",", data)
                if match:
                    vid = match.group(1)
                else:
                    log.error("Can't find video file")
                    sys.exit(2)

        url = "http://premium.tv4play.se/api/web/asset/%s/play" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if sys.version_info < (2, 7):
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            if xml.find("live").text != "false":
                options.live = True

        streams = {}
        subtitle = False

        for i in sa:
            if i.find("mediaFormat").text != "smi":
                stream = {}
                stream["uri"] = i.find("base").text
                stream["path"] = i.find("url").text
                streams[int(i.find("bitrate").text)] = stream
            elif i.find("mediaFormat").text == "smi":
                subtitle = i.find("url").text
        if len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
        options.other = "-W %s -y %s" % (swf, test["path"])

        if test["uri"][0:4] == "rtmp":
            download_rtmp(options, test["uri"])
        elif test["uri"][len(test["uri"])-3:len(test["uri"])] == "f4m":
            match = re.search("\/se\/secure\/", test["uri"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["path"]
            download_hds(options, manifest, swf)
        if options.subtitle and subtitle:
            data = get_http_data(subtitle)
            subtitle_smi(options, data)

