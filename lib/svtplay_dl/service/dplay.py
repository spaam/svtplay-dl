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
from svtplay_dl.utils.urllib import quote, urlparse
from svtplay_dl.error import ServiceError
from svtplay_dl.utils import filenamify
from svtplay_dl.log import log

class Dplay(Service):
    supported_domains = ['dplay.se', 'dplay.dk', "dplay.no"]

    def get(self):
        data = self.get_urldata()
        premium = False
        parse = urlparse(self.url)
        domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)

        match = re.search(r"<link rel='shortlink' href='[^']+/\?p=(\d+)", data)
        if not match:
            match = re.search(r'data-video-id="([^"]+)"', data)
            if not match:
                yield ServiceError("Can't find video id")
                return
        vid = match.group(1)
        data = self.http.request("get", "http://%s/api/v2/ajax/videos?video_id=%s" % (parse.netloc, vid)).text
        dataj = json.loads(data)
        if dataj["data"] is None:
            yield ServiceError("Cant find video. wrong url without video?")
            return
        if self.options.username and self.options.password:
            premium = self._login(self.options)
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

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "dplay"
            name = self._autoname(dataj)
            if name is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "%s-%s-%s" % (name, vid, self.options.service)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        subt = "subtitles_%s_srt" % self._country2lang()
        suburl = dataj["data"][0][subt]
        if len(suburl) > 0:
            yield subtitle(copy.copy(self.options), "raw", suburl)

        data = self.http.request("get", "http://geo.%s/geo.js" % domain).text
        dataj = json.loads(data)
        geo = dataj["countryCode"]
        timestamp = (int(time.time())+3600)*1000
        cookie = {"dsc-geo": quote('{"countryCode":"%s","expiry":%s}' % (geo, timestamp))}
        if self.options.cookies:
            self.options.cookies.update(cookie)
        else:
            self.options.cookies = cookie
        data = self.http.request("get", "https://secure.%s/secure/api/v2/user/authorization/stream/%s?stream_type=hds" % (domain, vid), cookies=self.options.cookies)
        if data.status_code == 403 or data.status_code == 401:
            yield ServiceError("Geoblocked video")
            return
        dataj = json.loads(data.text)
        if "hds" in dataj:
            streams = hdsparse(copy.copy(self.options), self.http.request("get", dataj["hds"], params={"hdcore": "3.8.0"}), dataj["hds"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        data = self.http.request("get", "https://secure.%s/secure/api/v2/user/authorization/stream/%s?stream_type=hls" % (domain, vid), cookies=self.options.cookies)
        dataj = json.loads(data.text)
        if "hls" in dataj:
            streams = hlsparse(self.options, self.http.request("get", dataj["hls"]), dataj["hls"])
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
        parse = urlparse(self.url)
        domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)
        data = self.http.request("get", "https://secure.%s/login/" % domain, cookies={})
        options.cookies = data.cookies
        match = re.search('realm_code" value="([^"]+)"', data.text)
        postdata = {"username" : options.username, "password": options.password, "remember_me": "true", "realm_code": match.group(1)}
        data = self.http.request("post", "https://secure.%s/secure/api/v1/user/auth/login" % domain, data=postdata, cookies=options.cookies)
        if data.status_code == 200:
            options.cookies = data.cookies
            return True
        else:
            return False

    def _country2lang(self):
        parse = urlparse(self.url)
        domain = re.search(r"dplay\.(\w\w)", parse.netloc).group(1)
        country = {"se": "sv", "no": "no", "dk": "da"}
        if domain and domain in country:
            return country[domain]
        else:
            return "sv"

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
        parse = urlparse(self.url)
        domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)
        match = re.search('data-show-id="([^"]+)"', data)
        if not match:
            log.error("Cant find show id")
            return None

        premium = None
        if options.username and options.password:
            premium = self._login(options)

        url = "http://www.%s/api/v2/ajax/shows/%s/seasons/?items=9999999&sort=episode_number_desc&page=" % (domain, match.group(1))
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
        if options.all_last > 0:
            return episodes[:options.all_last]
        return episodes
