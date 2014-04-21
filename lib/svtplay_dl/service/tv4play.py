# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import xml.etree.ElementTree as ET
import json

from svtplay_dl.utils.urllib import urlparse, parse_qs, quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, is_py2_old
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import HDS
from svtplay_dl.subtitle import subtitle_smi

class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4play.se', 'tv4.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        parse = urlparse(self.url)
        if "tv4play.se" in self.url:
            try:
                vid = parse_qs(parse[4])["video_id"][0]
            except KeyError:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            match = re.search(r"-(\d+)$", self.url)
            if match:
                vid = match.group(1)
            else:
                match = re.search(r"\"vid\":\"(\d+)\",", self.get_urldata())
                if match:
                    vid = match.group(1)
                else:
                    log.error("Can't find video file")
                    sys.exit(2)

        url = "http://premium.tv4play.se/api/web/asset/%s/play" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if is_py2_old:
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            if xml.find("live").text != "false":
                options.live = True

        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                base = i.find("base").text
                if base[0:4] == "rtmp":
                    swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
                    options.other = "-W %s -y %s" % (swf, i.find("url").text)
                    yield RTMP(options, i.find("base").text, i.find("bitrate").text)
                elif base[len(base)-3:len(base)] == "f4m":
                    manifest = "%s?hdcore=2.8.0&g=hejsan" % i.find("url").text
                    yield HDS(options, manifest, "0")
            elif i.find("mediaFormat").text == "smi":
                yield subtitle_smi(i.find("url").text)

    def find_all_episodes(self, options):
        parse =  urlparse(self.url)
        show = quote_plus(parse.path[parse.path.find("/", 1)+1:])
        data = get_http_data("http://webapi.tv4play.se/play/video_assets?type=episode&is_live=false&platform=web&node_nids=%s&per_page=99999" % show)
        jsondata = json.loads(data)
        episodes = []
        for i in jsondata["results"]:
            try:
                days = int(i["availability"]["availability_group_free"])
            except ValueError:
                days = 999
            if  days > 0:
                id = i["id"]
                url = "http://www.tv4play.se/program/%s?video_id=%s" % (show, id)
                episodes.append(url)
        return sorted(episodes)