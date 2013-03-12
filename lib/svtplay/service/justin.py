# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
from urlparse import urlparse
import xml.etree.ElementTree as ET

from svtplay.utils import get_http_data, select_quality
from svtplay.log import log
from svtplay.fetcher.rtmp import download_rtmp
from svtplay.fetcher.http import download_http

class Justin():
    def handle(self, url):
        return ("twitch.tv" in url) or ("justin.tv" in url)

    def get(self, options, url):
        parse = urlparse(url)
        match = re.search("/b/(\d+)", parse.path)
        if match:
            url = "http://api.justin.tv/api/broadcast/by_archive/%s.xml?onsite=true" % match.group(1)
            data = get_http_data(url)
            xml = ET.XML(data)
            url = xml.find("archive").find("video_file_url").text

            download_http(options, url)
        else:
            match = re.search("/(.*)", parse.path)
            if match:
                user = match.group(1)
                data = get_http_data(url)
                match = re.search("embedSWF\(\"(.*)\", \"live", data)
                if not match:
                    log.error("Can't find swf file.")
                options.other = match.group(1)
                url = "http://usher.justin.tv/find/%s.xml?type=any&p=2321" % user
                options.live = True
                data = get_http_data(url)
                data = re.sub("<(\d+)", "<_\g<1>", data)
                data = re.sub("</(\d+)", "</_\g<1>", data)
                xml = ET.XML(data)
                if sys.version_info < (2, 7):
                    sa = list(xml)
                else:
                    sa = list(xml)
                streams = {}
                for i in sa:
                    if i.tag[1:][:-1] != "iv":
                        try:
                            stream = {}
                            stream["token"] = i.find("token").text
                            stream["url"] = "%s/%s" % (i.find("connect").text, i.find("play").text)
                            streams[int(i.find("video_height").text)] = stream
                        except AttributeError:
                            pass
                if len(streams) > 0:
                    test = select_quality(options, streams)
                    options.other = "-j '%s' -W %s" % (test["token"], options.other)
                    options.resume = False
                    download_rtmp(options, test["url"])
                else:
                    log.error("Can't any streams")
                    sys.exit(2)
