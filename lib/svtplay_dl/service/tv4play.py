# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import os
import xml.etree.ElementTree as ET
import json
import copy

from svtplay_dl.utils.urllib import urlparse, parse_qs, quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, is_py2_old, filenamify
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import hlsparse, HLS
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
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
                vid = parse_qs(parse.query)["video_id"][0]
            except KeyError:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            match = re.search(r"\"vid\":\"(\d+)\",", self.get_urldata())
            if match:
                vid = match.group(1)
            else:
                match = re.search(r"-(\d+)$", self.url)
                if match:
                    vid = match.group(1)
                else:
                    log.error("Can't find video id")
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
        if xml.find("drmProtected").text == "true":
            log.error("DRM protected content.")
            sys.exit(2)

        if options.output_auto:
            directory = os.path.dirname(options.output)
            options.service = "tv4play"
            title = "%s-%s-%s" % (options.output, vid, options.service)
            title = filenamify(title)
            if len(directory):
                options.output = "%s/%s" % (directory, title)
            else:
                options.output = title

        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                base = urlparse(i.find("base").text)
                parse = urlparse(i.find("url").text)
                if base.scheme == "rtmp":
                    swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
                    options.other = "-W %s -y %s" % (swf, i.find("url").text)
                    yield RTMP(copy.copy(options), i.find("base").text, i.find("bitrate").text)
                elif parse.path[len(parse.path)-3:len(parse.path)] == "f4m":
                    query = ""
                    if i.find("url").text[-1] != "?":
                        query = "?"
                    manifest = "%s%shdcore=2.8.0&g=hejsan" % (i.find("url").text, query)
                    streams = hdsparse(copy.copy(options), manifest)
                    for n in list(streams.keys()):
                        yield streams[n]
            elif i.find("mediaFormat").text == "smi":
                yield subtitle_smi(i.find("url").text)

        url = "http://premium.tv4play.se/api/web/asset/%s/play?protocol=hls" % vid
        data = get_http_data(url)
        xml = ET.XML(data)
        ss = xml.find("items")
        if is_py2_old:
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))
        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                parse = urlparse(i.find("url").text)
                if parse.path.endswith("m3u8"):
                    streams = hlsparse(i.find("url").text)
                    for n in list(streams.keys()):
                        yield HLS(copy.copy(options), streams[n], n)

    def find_all_episodes(self, options):
        parse =  urlparse(self.url)
        show = parse.path[parse.path.find("/", 1)+1:]
        if not re.search("%", show):
            show = quote_plus(show)
        data = get_http_data("http://webapi.tv4play.se/play/video_assets?type=episode&is_live=false&platform=web&node_nids=%s&per_page=99999" % show)
        jsondata = json.loads(data)
        episodes = []
        for i in jsondata["results"]:
            try:
                days = int(i["availability"]["availability_group_free"])
            except ValueError:
                days = 999
            if  days > 0:
                video_id = i["id"]
                url = "http://www.tv4play.se/program/%s?video_id=%s" % (
                    show, video_id)
                episodes.append(url)
        return sorted(episodes)
