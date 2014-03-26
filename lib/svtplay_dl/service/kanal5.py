# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import json

from svtplay_dl.utils.urllib import CookieJar, Cookie
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data, select_quality, subtitle_json
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import download_rtmp
from svtplay_dl.fetcher.hls import download_hls

class Kanal5(Service):
    supported_domains = ['kanal5play.se', 'kanal9play.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.cj = CookieJar()
        self.subtitle = None

    def get(self, options):
        match = re.search(r".*video/([0-9]+)", self.url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)

        video_id = match.group(1)
        if options.username and options.password:
            #bogus
            cc = Cookie(None, 'asdf', None, '80', '80', 'www.kanal5play.se', None, None, '/', None, False, False, 'TestCookie', None, None, None)
            self.cj.set_cookie(cc)
            #get session cookie
            data = get_http_data("http://www.kanal5play.se/", cookiejar=self.cj)
            authurl = "https://kanal5swe.appspot.com/api/user/login?callback=jQuery171029989&email=%s&password=%s&_=136250" % (options.username, options.password)
            data = get_http_data(authurl)
            match = re.search(r"({.*})\);", data)
            jsondata = json.loads(match.group(1))
            if jsondata["success"] == False:
                log.error(jsondata["message"])
                sys.exit(2)
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

        format_ = "FLASH"
        if options.hls:
            format_ = "IPHONE"
        url = "http://www.kanal5play.se/api/getVideo?format=%s&videoId=%s" % (format_, video_id)
        data = json.loads(get_http_data(url, cookiejar=self.cj))
        if not options.live:
            options.live = data["isLive"]
        if data["hasSubtitle"]:
            self.subtitle = "http://www.kanal5play.se/api/subtitles/%s" % video_id

        if options.subtitle and options.force_subtitle:
            return

        if options.hls:
            url = data["streams"][0]["source"]
            if data["streams"][0]["drmProtected"]:
                log.error("We cant download drm files for this site.")
                sys.exit(2)
            download_hls(options, url)
        else:
            streams = {}

            for i in data["streams"]:
                stream = {}
                if i["drmProtected"]:
                    log.error("We cant download drm files for this site.")
                    sys.exit(2)
                stream["source"] = i["source"]
                streams[int(i["bitrate"])] = stream

            steambaseurl = data["streamBaseUrl"]

            test = select_quality(options, streams)

            filename = test["source"]
            match = re.search(r"^(.*):", filename)
            options.other = "-W %s -y %s " % ("http://www.kanal5play.se/flash/K5StandardPlayer.swf", filename)
            download_rtmp(options, steambaseurl)

    def get_subtitle(self, options):
        if self.subtitle:
            data = get_http_data(self.subtitle, cookiejar=self.cj)
            subtitle_json(options, data)
