# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import json
import time
import os

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.urllib import quote
from svtplay_dl.error import ServiceError
from svtplay_dl.utils import filenamify
from svtplay_dl.log import log

class Dplay(Service):
    supported_domains = ['dplay.se']

    def get(self, options):
        data = self.get_urldata()
        premium = False
        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        match = re.search("<link rel='shortlink' href='http://www.dplay.se/\?p=(\d+)", data)
        if not match:
            yield ServiceError("Can't find video id")
            return
        vid = match.group(1)
        data = self.http.request("get", "http://www.dplay.se/api/v2/ajax/videos?video_id=%s" % vid).text
        dataj = json.loads(data)
        if dataj["data"] == None:
            yield ServiceError("Cant find video. wrong url without video?")
            return
        if options.username and options.password:
            premium = self._login(options)
            if not premium:
                yield ServiceError("Wrong username or password")
                return

        what = self._playable(dataj, premium)
        if what == 1:
            yield ServiceError("Premium content")
            return
        if what == 2:
            yield ServiceError("DRM protected. Can't do anything")
            return

        if options.output_auto:
            directory = os.path.dirname(options.output)
            options.service = "dplay"
            name = self._autoname(dataj)
            if name is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "%s-%s-%s" % (name, vid, options.service)
            if len(directory):
                options.output = os.path.join(directory, title)
            else:
                options.output = title
        suburl = dataj["data"][0]["subtitles_sv_srt"]
        if len(suburl) > 0:
            yield subtitle(copy.copy(options), "raw", suburl)

        if options.force_subtitle:
            return

        data = self.http.request("get", "http://geo.dplay.se/geo.js").text
        dataj = json.loads(data)
        geo = dataj["countryCode"]
        timestamp = (int(time.time())+3600)*1000
        cookie = {"dsc-geo": quote('{"countryCode":"%s","expiry":%s}' % (geo, timestamp))}
        if options.cookies:
            options.cookies.update(cookie)
        else:
            options.cookies = cookie
        data = self.http.request("get", "https://secure.dplay.se/secure/api/v2/user/authorization/stream/%s?stream_type=hds" % vid, cookies=options.cookies)
        dataj = json.loads(data.text)
        if "hds" in dataj:
            streams = hdsparse(copy.copy(options), self.http.request("get", dataj["hds"], params={"hdcore": "3.8.0"}), dataj["hds"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        data = self.http.request("get", "https://secure.dplay.se/secure/api/v2/user/authorization/stream/%s?stream_type=hls" % vid, cookies=options.cookies)
        dataj = json.loads(data.text)
        if "hls" in dataj:
            streams = hlsparse(options, self.http.request("get", dataj["hls"]), dataj["hls"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]

    def _autoname(self, jsondata):
        show = jsondata["data"][0]["video_metadata_show"]
        season = jsondata["data"][0]["season"]
        episode = jsondata["data"][0]["episode"]
        title = jsondata["data"][0]["title"]
        return filenamify("%s.s%se%s.%s" % (show, season, episode, title))

    def _login(self, options):
        data = self.http.request("get", "https://secure.dplay.se/login/", cookies={})
        options.cookies = data.cookies
        match = re.search('realm_code" value="([^"]+)"', data.text)
        postdata = {"username" : options.username, "password": options.password, "remember_me": "true", "realm_code": match.group(1)}
        data = self.http.request("post", "https://secure.dplay.se/secure/api/v1/user/auth/login", data=postdata, cookies=options.cookies)
        if data.status_code == 200:
            options.cookies = data.cookies
            return True
        else:
            return False

    def _playable(self, dataj, premium):
        if dataj["data"][0]["content_info"]["package_label"]["value"] == "Premium" and not premium:
            return 1

        if dataj["data"][0]["video_metadata_drmid_playready"] != "none":
            return 2

        if dataj["data"][0]["video_metadata_drmid_flashaccess"] != "none":
            return 2
        return 0

    def find_all_episodes(self, options):
        data = self.get_urldata()
        match = re.search('data-show-id="([^"]+)"', data)
        if not match:
            log.error("Cant find show id")
            return None

        premium = None
        if options.username and options.password:
            premium = self._login(options)

        url = "http://www.dplay.se/api/v2/ajax/shows/%s/seasons/?items=9999999&sort=episode_number_desc&page=" % match.group(1)
        episodes = []
        page = 0
        data = self.http.request("get", "%s%s" % (url, page)).text
        dataj = json.loads(data)
        for i in dataj["data"]:
            what = self._playable(dataj, premium)
            if what == 0:
                episodes.append(i["url"])
        pages = dataj["total_pages"]
        for n in range(1, pages):
            data = self.http.request("get", "%s%s" % (url, n)).text
            dataj = json.loads(data)
            for i in dataj["data"]:
                what = self._playable(dataj, premium)
                if what == 0:
                    episodes.append(i["url"])
        if len(episodes) == 0:
            log.error("Cant find any playable files")
        return episodes
