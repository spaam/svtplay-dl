from __future__ import absolute_import
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
        error, data = self.get_urldata()
        if error:
            log.error("Can't get the page")
            return
        match = re.search(r'mrss\s+:\s+"([^"]+)"', data)
        if not match:
            log.error("Can't find id for the video")
            return
        swfurl = re.search(r'embedSWF\( "([^"]+)"', self.get_urldata()[1])
        options.other = "-W %s" % swfurl.group(1)
        error, data = get_http_data(match.group(1))
        if error:
            log.error("Cant get video info")
            return
        xml = ET.XML(data)
        mediagen = xml.find("channel").find("item").find("{http://search.yahoo.com/mrss/}group")
        title = xml.find("channel").find("item").find("title").text
        if options.output_auto:
            directory = os.path.dirname(options.output)
            if len(directory):
                options.output = "%s/%s" % (directory, title)
            else:
                options.output = title

        if self.exclude(options):
            return

        contenturl = mediagen.find("{http://search.yahoo.com/mrss/}content").attrib["url"]
        error, content = get_http_data(contenturl)
        if error:
            log.error("Cant download stream info")
            return
        xml = ET.XML(content)
        ss = xml.find("video").find("item")
        if is_py2_old:
            sa = list(ss.getiterator("rendition"))
        else:
            sa = list(ss.iter("rendition"))

        for i in sa:
            yield RTMP(options, i.find("src").text, i.attrib["bitrate"])

    def find_all_episodes(self, options):
        match = re.search(r"data-franchise='([^']+)'", self.get_urldata()[1])
        if match is None:
            log.error("Couldn't program id")
            return
        programid = match.group(1)
        match = re.findall(r"<li class='(divider playlist-item|playlist-item)'( data-item-id='([^']+)')?", self.get_urldata()[1])
        if not match:
            log.error("Couldn't retrieve episode list")
            return
        episodNr = []
        for i in match:
            if i[0] == "playlist-item":
                episodNr.append(i[2])
            else:
                break

        episodes = []
        n = 0
        for i in sorted(episodNr):
            if n == options.all_last:
                break
            episodes.append("http://www.nickelodeon.se/serier/%s-something/videos/%s-something" % (programid, i))
            n += 1
        return episodes
