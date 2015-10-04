# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy
import os

from svtplay_dl.service import Service
from svtplay_dl.utils import filenamify
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Kanal5(Service):
    supported_domains = ['kanal5play.se', 'kanal9play.se', 'kanal11play.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.cookies = {}
        self.subtitle = None

    def get(self, options):
        match = re.search(r".*video/([0-9]+)", self.url)
        if not match:
            yield ServiceError("Can't find video file")
            return

        video_id = match.group(1)
        if options.username and options.password:
            # get session cookie
            data = self.http.request("get", "http://www.kanal5play.se/", cookies=self.cookies)
            authurl = "https://kanal5swe.appspot.com/api/user/login?callback=jQuery171029989&email=%s&password=%s&_=136250" % \
                      (options.username, options.password)
            data = self.http.request("get", authurl, cookies=data.cookies).text
            match = re.search(r"({.*})\);", data)
            jsondata = json.loads(match.group(1))
            if jsondata["success"] is False:
                yield ServiceError(jsondata["message"])
                return
            authToken = jsondata["userData"]["auth"]
            self.cookies = {"authToken": authToken}
            options.cookies = self.cookies

        url = "http://www.kanal5play.se/api/getVideo?format=FLASH&videoId=%s" % video_id
        data = self.http.request("get", url, cookies=self.cookies).text
        data = json.loads(data)
        options.cookies = self.cookies
        if not options.live:
            options.live = data["isLive"]

        if options.output_auto:
            directory = os.path.dirname(options.output)
            options.service = "kanal5"

            title = "%s-s%s-%s-%s-%s" % (data["program"]["name"], data["seasonNumber"], data["episodeText"], data["id"], options.service)
            title = filenamify(title)
            if len(directory):
                options.output = os.path.join(directory, title)
            else:
                options.output = title

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        if data["hasSubtitle"]:
            yield subtitle(copy.copy(options), "json", "http://www.kanal5play.se/api/subtitles/%s" % video_id)

        if options.force_subtitle:
            return

        show = True
        if "streams" in data.keys():
            for i in data["streams"]:
                if i["drmProtected"]:
                    yield ServiceError("We cant download drm files for this site.")
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
            data = self.http.request("get", url, cookies=self.cookies)
            data = json.loads(data.text)
            if "reasonsForNoStreams" in data:
                show = False
            if "streams" in data.keys():
                for i in data["streams"]:
                    streams = hlsparse(options, self.http.request("get", i["source"]), i["source"])
                    for n in list(streams.keys()):
                        yield streams[n]
        if "reasonsForNoStreams" in data and show:
            yield ServiceError(data["reasonsForNoStreams"][0])

    def find_all_episodes(self, options):
        program = re.search(".*/program/(\d+)", self.url)
        if not program:
            log.error("Can't find program id in url")
            return None
        baseurl = "http://www.kanal5play.se/content/program/%s" % program.group(1)
        data = self.http.request("get", baseurl).text
        sasong = re.search("/program/\d+/sasong/(\d+)", data)
        if not sasong:
            log.error("Can't find seasong id")
            return None
        seasong = int(sasong.group(1))
        episodes = []
        n = 0
        more = True
        while more:
            url = "%s/sasong/%s" % (baseurl, seasong)
            data = self.http.request("get", url)
            if data.status_code == 404:
                more = False
            else:
                regex = re.compile(r'href="(/play/program/\d+/video/\d+)"')
                for match in regex.finditer(data.text):
                    if n == options.all_last:
                        break
                    url2 = "http://www.kanal5play.se%s" % match.group(1)
                    if url2 not in episodes:
                        episodes.append(url2)
                    n += 1
                seasong -= 1

        return episodes
