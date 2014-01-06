from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality, is_py2_old
from svtplay_dl.fetcher.http import download_http

from svtplay_dl.log import log

class Mtvservices(Service):
    supported_domains = ['colbertnation.com', 'thedailyshow.com']

    def get(self, options):
        data = get_http_data(self.url)
        match = re.search(r"mgid=\"(mgid.*[0-9]+)\" data-wi", data)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)
        url = "http://media.mtvnservices.com/player/html5/mediagen/?uri=%s" % match.group(1)
        data = get_http_data(url)
        start = data.index("<?xml version=")
        data = data[start:]
        xml = ET.XML(data)
        ss = xml.find("video").find("item")
        if is_py2_old:
            sa = list(ss.getiterator("rendition"))
        else:
            sa = list(ss.iter("rendition"))
        streams = {}
        for i in sa:
            streams[int(i.attrib["height"])] = i.find("src").text
        if len(streams) == 0:
            log.error("Can't find video file: %s", ss.text)
            sys.exit(2)
        stream = select_quality(options, streams)
        temp = stream.index("gsp.comedystor")
        url = "http://mtvnmobile.vo.llnwd.net/kip0/_pxn=0+_pxK=18639+_pxE=mp4/44620/mtvnorigin/%s" % stream[temp:]
        download_http(options, url)
