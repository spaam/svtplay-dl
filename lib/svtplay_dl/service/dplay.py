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
from svtplay_dl.utils import filenamify, is_py2
from svtplay_dl.log import log

class Dplay(Service):
    supported_domains = ['dplay.se', 'dplay.dk', "dplay.no"]

    def get(self):
        data = self.get_urldata()
        premium = False
        channel = False
        parse = urlparse(self.url)
        domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)

        match = re.search(r"<link rel='shortlink' href='[^']+/\?p=(\d+)", data)
        if not match:
            match = re.search(r'data-video-id="([^"]+)"', data)
            if not match:
                match = re.search(r'page-id-(\d+) ', data)
                if not match:
                    yield ServiceError("Can't find video id")
                    return
                channel = True
                self.options.live = True
        vid = match.group(1)
        data = self.http.request("get", "http://{0}/api/v2/ajax/videos?video_id={1}".format(parse.netloc, vid)).text
        dataj = json.loads(data)
        if not channel and dataj["data"] is None:
            yield ServiceError("Cant find video. wrong url without video?")
            return
        if self.options.username and self.options.password:
            premium = self._login(self.options)
            if not premium:
                yield ServiceError("Wrong username or password")
                return

        if not channel:
            what = self._playable(dataj["data"][0], premium)
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
                title = "{0}-{1}-{2}".format(name, vid, self.options.service)
                if len(directory):
                    self.options.output = os.path.join(directory, title)
                else:
                    self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        if not channel:
            subt = "subtitles_{0}_srt".format(self._country2lang())
            suburl = dataj["data"][0][subt]
            if len(suburl) > 0:
                yield subtitle(copy.copy(self.options), "raw", suburl)

        data = self.http.request("get", "http://geo.{0}/geo.js".format(domain)).text
        dataj = json.loads(data)
        geo = dataj["countryCode"]
        timestamp = (int(time.time())+3600)*1000
        cookie = {"dsc-geo": quote('{{"countryCode":"{0}","expiry":{1}}}'.format(geo, timestamp))}
        if self.options.cookies:
            self.options.cookies.update(cookie)
        else:
            self.options.cookies = cookie
        data = self.http.request("get", "https://secure.{0}/secure/api/v2/user/authorization/stream/{1}?stream_type=hds".format(domain, vid), cookies=self.options.cookies)
        if data.status_code == 403 or data.status_code == 401:
            yield ServiceError("Geoblocked video")
            return
        dataj = json.loads(data.text)
        if not channel and "hds" in dataj:
            streams = hdsparse(copy.copy(self.options), self.http.request("get", dataj["hds"], params={"hdcore": "3.8.0"}), dataj["hds"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
        data = self.http.request("get", "https://secure.{0}/secure/api/v2/user/authorization/stream/{1}?stream_type=hls".format(domain, vid), cookies=self.options.cookies)
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
        if is_py2:
            show = filenamify(show).encode("latin1")
            title = filenamify(title).encode("latin1")
        else:
            show = filenamify(show)
            title = filenamify(title)
        return filenamify("{0}.s{1:02d}e{2:02d}.{3}".format(show, int(season), int(episode), title))

    def _login(self, options):
        parse = urlparse(self.url)
        domain = re.search(r"(dplay\.\w\w)", parse.netloc).group(1)
        data = self.http.request("get", "https://secure.{0}/login/".format(domain), cookies={})
        options.cookies = data.cookies
        match = re.search('realm_code" value="([^"]+)"', data.text)
        postdata = {"username" : options.username, "password": options.password, "remember_me": "true", "realm_code": match.group(1)}
        data = self.http.request("post", "https://secure.{0}/secure/api/v1/user/auth/login".format(domain), data=postdata, cookies=options.cookies)
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
        if dataj["content_info"]["package_label"]["value"] == "Premium" and not premium:
            return 1

        if dataj["video_metadata_drmid_playready"] != "none":
            return 2

        if dataj["video_metadata_drmid_flashaccess"] != "none":
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

        url = "http://www.{0}/api/v2/ajax/shows/{1}/seasons/?items=9999999&sort=episode_number_desc&page=".format(domain, match.group(1))
        episodes = []
        page = 0
        data = self.http.request("get", "{0}{1}".format(url, page)).text
        dataj = json.loads(data)
        for i in dataj["data"]:
            what = self._playable(i, premium)
            if what == 0:
                episodes.append(i["url"])
        pages = dataj["total_pages"]
        for n in range(1, pages):
            data = self.http.request("get", "{0}{1}".format(url, n)).text
            dataj = json.loads(data)
            for i in dataj["data"]:
                what = self._playable(i, premium)
                if what == 0:
                    episodes.append(i["url"])
        if len(episodes) == 0:
            log.error("Cant find any playable files")
        if options.all_last > 0:
            return episodes[:options.all_last]
        return episodes
