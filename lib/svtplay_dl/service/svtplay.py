# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import json
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import get_http_data, select_quality, subtitle_wsrt
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hds import download_hds
from svtplay_dl.fetcher.hls import download_hls
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.http import download_http

from svtplay_dl.log import log

class Svtplay(Service, OpenGraphThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'oppetarkiv.se', 'beta.svtplay.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        if re.findall("svt.se", self.url):
            match = re.search(r"data-json-href=\"(.*)\"", self.get_urldata())
            if match:
                filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
                url = "http://www.svt.se%s" % filename
            else:
                log.error("Can't find video file")
                sys.exit(2)
        else:
            url = self.url

        pos = url.find("?")
        if pos < 0:
            dataurl = "%s?&output=json&format=json" % url
        else:
            dataurl = "%s&output=json&format=json" % url
        data = json.loads(get_http_data(dataurl))
        if "live" in data["video"]:
            options.live = data["video"]["live"]
        else:
            options.live = False

        if data["video"]["subtitleReferences"]:
            try:
                self.subtitle = data["video"]["subtitleReferences"][0]["url"]
            except (KeyError, NoneType):
                pass

        streams = {}
        streams2 = {} #hack..
        for i in data["video"]["videoReferences"]:
            parse = urlparse(i["url"])
            if options.hls and parse.path[len(parse.path)-4:] == "m3u8":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            elif not options.hls and parse.path[len(parse.path)-3:] == "f4m":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            elif not options.hls and parse.path[len(parse.path)-3:] != "f4m" and parse.path[len(parse.path)-4:] != "m3u8":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            if options.hls and parse.path[len(parse.path)-3:] == "f4m":
                stream = {}
                stream["url"] = i["url"]
                streams2[int(i["bitrate"])] = stream

        if len(streams) == 0 and options.hls:
            if len(streams) == 0:
                log.error("Can't find any streams.")
                sys.exit(2)
            test = streams2[0]
            test["url"] = test["url"].replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        elif len(streams) == 0:
            log.error("Can't find any streams.")
            sys.exit(2)
        elif len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        if options.subtitle and options.force_subtitle:
            return

        parse = urlparse(test["url"])
        if parse.scheme == "rtmp":
            embedurl = "%s?type=embed" % url
            data = get_http_data(embedurl)
            match = re.search(r"value=\"(/(public)?(statiskt)?/swf(/video)?/svtplayer-[0-9\.a-f]+swf)\"", data)
            swf = "http://www.svtplay.se%s" % match.group(1)
            options.other = "-W %s" % swf
            download_rtmp(options, test["url"])
        elif options.hls:
            download_hls(options, test["url"])
        elif parse.path[len(parse.path)-3:] == "f4m":
            match = re.search(r"\/se\/secure\/", test["url"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["url"]
            download_hds(options, manifest)
        else:
            download_http(options, test["url"])


    def get_subtitle(self, options):
        if self.subtitle:
            if options.output != "-":
                data = get_http_data(self.subtitle)
                subtitle_wsrt(options, data)


    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
        if match is None:
            log.error("Couldn't retrieve episode list")
            sys.exit(2)

        xml = ET.XML(get_http_data(match.group(1)))

        return sorted(x.text for x in xml.findall(".//item/link"))
