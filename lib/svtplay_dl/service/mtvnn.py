from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, is_py2_old
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP

# This is _very_ similar to mtvservices..
class Mtvnn(Service, OpenGraphThumbMixin):
    supported_domains = ['nickelodeon.se', "nickelodeon.nl", "nickelodeon.no"]

    def get(self, options):
        match = re.search(r'mrss\s+:\s+"([^"]+)"', self.get_urldata())
        if not match:
            log.error("Can't find id for the video")
            sys.exit(2)
        swfurl = re.search(r'embedSWF\( "([^"]+)"', self.get_urldata())
        options.other = "-W %s" % swfurl.group(1)
        data = get_http_data(match.group(1))
        xml = ET.XML(data)
        mediagen = xml.find("channel").find("item").find("{http://search.yahoo.com/mrss/}group")
        contenturl = mediagen.find("{http://search.yahoo.com/mrss/}content").attrib["url"]
        content = get_http_data(contenturl)
        xml = ET.XML(content)
        ss = xml.find("video").find("item")
        if is_py2_old:
            sa = list(ss.getiterator("rendition"))
        else:
            sa = list(ss.iter("rendition"))

        for i in sa:
            yield RTMP(options, i.find("src").text, i.attrib["bitrate"])