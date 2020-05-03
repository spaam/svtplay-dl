# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import re
import xml.etree.ElementTree as ET

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import Service


class Mtvservices(Service):
    supported_domains = ["colbertnation.com", "thedailyshow.com"]

    def get(self):
        data = self.get_urldata()

        match = re.search(r"mgid=\"(mgid.*[0-9]+)\" data-wi", data)
        if not match:
            yield ServiceError("Can't find video file")
            return
        url = "http://media.mtvnservices.com/player/html5/mediagen/?uri=%s" % match.group(1)
        data = self.http.request("get", url)
        start = data.index("<?xml version=")
        data = data[start:]
        xml = ET.XML(data)
        ss = xml.find("video").find("item")
        sa = list(ss.iter("rendition"))

        for i in sa:
            temp = i.find("src").text.index("gsp.comedystor")
            url = "http://mtvnmobile.vo.llnwd.net/kip0/_pxn=0+_pxK=18639+_pxE=mp4/44620/mtvnorigin/{}".format(i.find("src").text[temp:])
            yield HTTP(copy.copy(self.config), url, i.attrib["height"], output=self.output)
