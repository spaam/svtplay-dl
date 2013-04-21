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
    def handle(self, url):
        return ("kanal5play.se" in url) or ('kanal9play.se' in url)

    def get(self, options, url):
        cj = CookieJar()
        match = re.search(".*video/([0-9]+)", url)
        if not match:
            log.error("Can't find video file")
            sys.exit(2)

        video_id = match.group(1)
        if options.username and options.password:
            #bogus
            cc = Cookie(None, 'asdf', None, '80', '80', 'www.kanal5play.se', None, None, '/', None, False, False, 'TestCookie', None, None, None)
            cj.set_cookie(cc)
            #get session cookie
            data = get_http_data("http://www.kanal5play.se/", cookiejar=cj)
            authurl = "https://kanal5swe.appspot.com/api/user/login?callback=jQuery171029989&email=%s&password=%s&_=136250" % (options.username, options.password)
            data = get_http_data(authurl)
            match = re.search("({.*})\);", data)
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
            cj.set_cookie(cc)

        format = "FLASH"
        if options.hls:
            format = "IPHONE"
        url = "http://www.kanal5play.se/api/getVideo?format=%s&videoId=%s" % (format, video_id)
        data = json.loads(get_http_data(url, cookiejar=cj))
        options.live = data["isLive"]
        if data["hasSubtitle"]:
            subtitle = "http://www.kanal5play.se/api/subtitles/%s" % video_id
        if options.hls:
            url = data["streams"][0]["source"]
            baseurl = url[0:url.rfind("/")]
            if data["streams"][0]["drmProtected"]:
                log.error("We cant download drm files for this site.")
                sys.exit(2)
            download_hls(options, url, baseurl)
        else:
            steambaseurl = data["streamBaseUrl"]
            streams = {}

            for i in data["streams"]:
                stream = {}
                stream["source"] = i["source"]
                streams[int(i["bitrate"])] = stream

            test = select_quality(options, streams)

            filename = test["source"]
            match = re.search("^(.*):", filename)
            options.other = "-W %s -y %s " % ("http://www.kanal5play.se/flash/K5StandardPlayer.swf", filename)
            download_rtmp(options, steambaseurl)
        if options.subtitle:
            if options.output != "-":
                data = get_http_data(subtitle, cookiejar=cj)
                subtitle_json(options, data)
