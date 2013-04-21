# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.http import download_http

if sys.version_info > (3, 0):
    from urllib.parse import urlparse, parse_qs, unquote_plus
else:
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus

class Sr():
    def handle(self, url):
        return "sverigesradio.se" in url

    def get(self, options, url):
        data = get_http_data(url)
        parse = urlparse(url)

        if "metafile" in parse_qs(parse.query):
            options.other = "%s?%s" % (parse.path, parse.query)
        else:
            match = re.search("linkUrl=(.*)\;isButton=", data)
            if not match:
                log.error("Can't find video file")
                sys.exit(2)
            options.other = unquote_plus(match.group(1))

        url = "http://sverigesradio.se%s" % options.other
        data = get_http_data(url)
        xml = ET.XML(data)
        url = xml.find("entry").find("ref").attrib["href"]
        download_http(options, url)

