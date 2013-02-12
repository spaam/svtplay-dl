import sys
import re
import xml.etree.ElementTree as ET

from lib.svtplay.utils import get_http_data
from lib.svtplay.log import log
from lib.svtplay.http import download_http

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
        try:
            metafile = parse_qs(parse[4])["metafile"][0]
            options.other = "%s?%s" % (parse[2], parse[4])
        except KeyError:
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

