# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp

class Qbrick(Service):
    def handle(self, url):
        return ("dn.se" in url) or ("di.se" in url) or ("svd.se" in url) or ("sydsvenskan.se" in url)

    def get(self, options, url):
        if re.findall(r"sydsvenskan.se", url):
            data = get_http_data(url)
            match = re.search(r"data-qbrick-mcid=\"([0-9A-F]+)\"", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            mcid = match.group(1)
            host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/%s" % mcid
        elif re.findall(r"di.se", url):
            data = get_http_data(url)
            match = re.search("src=\"(http://qstream.*)\"></iframe", data)
            if not match:
                log.error("Can't find video info")
                sys.exit(2)
            data = get_http_data(match.group(1))
            match = re.search(r"data-qbrick-ccid=\"([0-9A-Z]+)\"", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            host = "http://vms.api.qbrick.com/rest/v3/getplayer/%s" % match.group(1)
        elif re.findall(r"dn.se", url):
            data = get_http_data(url)
            match = re.search(r"'([0-9A-F]{8})',", data)
            if not match:
                match = re.search(r"mediaId = '([0-9A-F]{8})';", data)
                if not match:
                    log.error("Can't find video file")
                    sys.exit(2)
            host = "http://vms.api.qbrick.com/rest/v3//getsingleplayer/%sDE1BA107?statusCode=xml" %  match.group(1)
        elif re.findall(r"svd.se", url):
            match = re.search(r"_([0-9]+)\.svd", url)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            data = get_http_data("http://www.svd.se/?service=ajax&type=webTvClip&articleId=%s" % match.group(1))
            match = re.search(r"mcid=([A-F0-9]+)\&width=", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            host = "http://vms.api.qbrick.com/rest/v3/getsingleplayer/%s" % match.group(1)
        else:
            log.error("Can't find site")
            sys.exit(2)

        data = get_http_data(host)
        xml = ET.XML(data)
        try:
            url = xml.find("media").find("item").find("playlist").find("stream").find("format").find("substream").text
        except AttributeError:
            log.error("Can't find video file")
            sys.exit(2)
        live = xml.find("media").find("item").find("playlist").find("stream").attrib["isLive"]
        if live == "true":
            options.live = True
        data = get_http_data(url)
        xml = ET.XML(data)
        server = xml.find("head").find("meta").attrib["base"]
        streams = xml.find("body").find("switch")
        if sys.version_info < (2, 7):
            sa = list(streams.getiterator("video"))
        else:
            sa = list(streams.iter("video"))
        streams = {}
        for i in sa:
            streams[int(i.attrib["system-bitrate"])] = i.attrib["src"]

        path = select_quality(options, streams)

        options.other = "-y %s" % path
        download_rtmp(options, server)

