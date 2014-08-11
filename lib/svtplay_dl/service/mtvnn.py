from __future__ import absolute_import
import sys
import re
import os
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
        title = xml.find("channel").find("item").find("title").text
        if options.output_auto:
            directory = os.path.dirname(options.output)
            if len(directory):
                options.output = "%s/%s" % (directory, title)
            else:
                options.output = title
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

    def find_all_episodes(self, options):
        match = re.search(r"data-franchise='([^']+)'", self.get_urldata())
        if match is None:
            log.error("Couldn't program id")
            sys.exit(2)
        programid = match.group(1)
        match = re.findall(r"data-item-id='([^']+)'", self.get_urldata())
        if not match:
            log.error("Couldn't retrieve episode list")
            sys.exit(2)
        episodes = []
        for i in sorted(match):
            episodes.append("http://www.nickelodeon.se/serier/%s-something/videos/%s-something" % (programid, i))
        return episodes
