import sys
import re
import json

from lib.svtplay.service import Service
from lib.svtplay.utils import get_http_data, select_quality

from lib.svtplay.hds import download_hds
from lib.svtplay.hls import download_hls
from lib.svtplay.rtmp import download_rtmp
from lib.svtplay.http import download_http

from lib.svtplay.log import log

class Svtplay(Service):
    def handle(self, url):
        return ("svtplay.se" in url) or ("svt.se" in url)

    def get(self, options, url):
        if re.findall("svt.se", url):
            data = get_http_data(url)
            match = re.search("data-json-href=\"(.*)\"", data)
            if match:
                filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
                url = "http://www.svt.se%s" % filename
            else:
                log.error("Can't find video file")
                sys.exit(2)
        url = "%s?type=embed" % url
        data = get_http_data(url)
        match = re.search("value=\"(/(public)?(statiskt)?/swf/video/svtplayer-[0-9\.]+swf)\"", data)
        swf = "http://www.svtplay.se%s" % match.group(1)
        options.other = "-W %s" % swf
        url = "%s&output=json&format=json" % url
        data = json.loads(get_http_data(url))
        options.live = data["video"]["live"]
        streams = {}
        streams2 = {} #hack..
        for i in data["video"]["videoReferences"]:
            if options.hls and i["playerType"] == "ios":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            elif not options.hls and i["playerType"] == "flash":
                stream = {}
                stream["url"] = i["url"]
                streams[int(i["bitrate"])] = stream
            if options.hls and i["playerType"] == "flash":
                stream = {}
                stream["url"] = i["url"]
                streams2[int(i["bitrate"])] = stream

        if len(streams) == 0 and options.hls:
            test = streams2[0]
            test["url"] = test["url"].replace("/z/", "/i/").replace("manifest.f4m", "master.m3u8")
        elif len(streams) == 0:
            log.error("Can't find any streams.")
            sys.exit(2)
        elif len(streams) == 1:
            test = streams[list(streams.keys())[0]]
        else:
            test = select_quality(options, streams)

        if test["url"][0:4] == "rtmp":
            download_rtmp(options, test["url"])
        elif options.hls:
            download_hls(options, test["url"])
        elif test["url"][len(test["url"])-3:len(test["url"])] == "f4m":
            match = re.search("\/se\/secure\/", test["url"])
            if match:
                log.error("This stream is encrypted. Use --hls option")
                sys.exit(2)
            manifest = "%s?hdcore=2.8.0&g=hejsan" % test["url"]
            download_hds(options, manifest, swf)
        else:
            download_http(options, test["url"])

