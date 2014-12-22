# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy
import os

from svtplay_dl.utils.urllib import CookieJar, Cookie
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, filenamify
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.subtitle import subtitle

class Kanal5(Service):
    supported_domains = ['kanal5play.se', 'kanal9play.se', 'kanal11play.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.cj = CookieJar()
        self.subtitle = None

    def get(self, options):
        match = re.search(r".*video/([0-9]+)", self.url)
        if not match:
            log.error("Can't find video file")
            return

        video_id = match.group(1)
        if options.username and options.password:
            # get session cookie
            error, data = get_http_data("http://www.kanal5play.se/", cookiejar=self.cj)
            authurl = "https://kanal5swe.appspot.com/api/user/login?callback=jQuery171029989&email=%s&password=%s&_=136250" % \
                      (options.username, options.password)
            error, data = get_http_data(authurl)
            match = re.search(r"({.*})\);", data)
            jsondata = json.loads(match.group(1))
            if jsondata["success"] is False:
                log.error(jsondata["message"])
                return
            authToken = jsondata["userData"]["auth"]
            cc = Cookie(version=0, name='authToken',
                        value=authToken,
                        port=None, port_specified=False,
                        domain='www.kanal5play.se',
                        domain_specified=True,
                        domain_initial_dot=True, path='/',
                        path_specified=True, secure=False,
                        expires=None, discard=True, comment=None,
                        comment_url=None, rest={'HttpOnly': None})
            self.cj.set_cookie(cc)
            options.cookies = self.cj

        url = "http://www.kanal5play.se/api/getVideo?format=FLASH&videoId=%s" % video_id
        error, data = get_http_data(url, cookiejar=self.cj)
        if error:
            log.error("Can't download video info")
            return
        data = json.loads(data)
        options.cookiejar = self.cj
        if not options.live:
            options.live = data["isLive"]

        if options.output_auto:
            directory = os.path.dirname(options.output)
            options.service = "kanal5"

            title = "%s-s%s-%s-%s-%s" % (data["program"]["name"], data["seasonNumber"], data["episodeText"], data["id"], options.service)
            title = filenamify(title)
            if len(directory):
                options.output = "%s/%s" % (directory, title)
            else:
                options.output = title

        if self.exclude(options):
            return

        if data["hasSubtitle"]:
            yield subtitle(copy.copy(options), "json", "http://www.kanal5play.se/api/subtitles/%s" % video_id)

        if options.force_subtitle:
            return

        if "streams" in data.keys():
            for i in data["streams"]:
                if i["drmProtected"]:
                    log.error("We cant download drm files for this site.")
                    return
                steambaseurl = data["streamBaseUrl"]
                bitrate = i["bitrate"]
                if bitrate > 1000:
                    bitrate = bitrate / 1000
                options2 = copy.copy(options)
                options2.other = "-W %s -y %s " % ("http://www.kanal5play.se/flash/K5StandardPlayer.swf", i["source"])
                options2.live = True
                yield RTMP(options2, steambaseurl, bitrate)

            url = "http://www.kanal5play.se/api/getVideo?format=IPAD&videoId=%s" % video_id
            error, data = get_http_data(url, cookiejar=self.cj)
            if error:
                log.error("Cant get video info")
                return
            data = json.loads(data)
            if "streams" in data.keys():
                for i in data["streams"]:
                    streams = hlsparse(i["source"])
                    for n in list(streams.keys()):
                        yield HLS(copy.copy(options), streams[n], n)
        if "reasonsForNoStreams" in data:
            log.error(data["reasonsForNoStreams"][0])
