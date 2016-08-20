# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os
import xml.etree.ElementTree as ET
import json
import copy

from svtplay_dl.utils.urllib import urlparse, parse_qs, quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import is_py2_old, is_py2, filenamify
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4play.se', 'tv4.se']

    def get(self):
        data = self.get_urldata()

        vid = findvid(self.url, data)
        if vid is None:
            yield ServiceError("Can't find video id for %s" % self.url)
            return

        if self.options.username and self.options.password:
            work = self._login(self.options.username, self.options.password)
            if isinstance(work, Exception):
                yield work
                return

        url = "http://prima.tv4play.se/api/web/asset/%s/play" % vid
        data = self.http.request("get", url, cookies=self.cookies)
        if data.status_code == 401:
            xml = ET.XML(data.content)
            code = xml.find("code").text
            if code == "SESSION_NOT_AUTHENTICATED":
                yield ServiceError("Can't access premium content")
            elif code == "ASSET_PLAYBACK_INVALID_GEO_LOCATION":
                yield ServiceError("Can't download this video because of geoblock.")
            else:
                yield ServiceError("Can't find any info for that video")
            return
        if data.status_code == 404:
            yield ServiceError("Can't find the video api")
            return
        xml = ET.XML(data.content)
        ss = xml.find("items")
        if is_py2_old:
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            if xml.find("live").text != "false":
                self.options.live = True
        if xml.find("drmProtected").text == "true":
            yield ServiceError("We cant download DRM protected content from this site.")
            return
        if xml.find("playbackStatus").text == "NOT_STARTED":
            yield ServiceError("Can't download something that is not started")
            return

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "tv4play"
            basename = self._autoname(vid)
            if basename is None:
                yield ServiceError("Cant find vid id for autonaming")
                return
            title = "%s-%s-%s" % (basename, vid, self.options.service)
            title = filenamify(title)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                base = urlparse(i.find("base").text)
                parse = urlparse(i.find("url").text)
                if "rtmp" in base.scheme:
                    swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
                    self.options.other = "-W %s -y %s" % (swf, i.find("url").text)
                    yield RTMP(copy.copy(self.options), i.find("base").text, i.find("bitrate").text)
                elif parse.path[len(parse.path)-3:len(parse.path)] == "f4m":
                    streams = hdsparse(self.options, self.http.request("get", i.find("url").text, params={"hdcore": "3.7.0"}), i.find("url").text)
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
            elif i.find("mediaFormat").text == "smi":
                yield subtitle(copy.copy(self.options), "smi", i.find("url").text)

        url = "https://prima.tv4play.se/api/web/asset/%s/play?protocol=hls" % vid
        data = self.http.request("get", url, cookies=self.cookies).content
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
                    streams = hlsparse(self.options, self.http.request("get", i.find("url").text), i.find("url").text)
                    for n in list(streams.keys()):
                        yield streams[n]

    def _get_show_info(self):
        show = self._get_showname(self.url)
        data = self.http.request("get", "http://webapi.tv4play.se/play/video_assets?type=episode&is_live=false&platform=web&node_nids=%s&per_page=99999" % show).text
        jsondata = json.loads(data)
        return jsondata

    def _get_clip_info(self, vid):
        show = self._get_showname(self.url)
        page = 1
        assets = page * 1000
        run = True
        while run:
            data = self.http.request("get", "http://webapi.tv4play.se/play/video_assets?type=clips&is_live=false&platform=web&node_nids=%s&per_page=1000&page=%s" % (show, page)).text
            jsondata = json.loads(data)
            for i in jsondata["results"]:
                if vid == i["id"]:
                    return i["title"]
            if not run:
                return None
            total = jsondata["total_hits"]
            if assets > total:
                run = False
            page += 1
            assets = page * 1000
        return None

    def _get_showname(self, url):
        parse = urlparse(self.url)
        if parse.path.count("/") > 2:
            match = re.search("^/([^/]+)/", parse.path)
            show = match.group(1)
        else:
            show = parse.path[parse.path.find("/", 1)+1:]
        if not re.search("%", show):
            if is_py2 and isinstance(show, unicode):
                show = show.encode("utf-8")
            show = quote_plus(show)
        return show

    def _autoname(self, vid):
        jsondata = self._get_show_info()
        for i in jsondata["results"]:
            if vid == i["id"]:
                return i["title"]
        return self._get_clip_info(vid)

    def _getdays(self, data, text):
        try:
            days = int(data["availability"][text])
        except (ValueError, TypeError):
            days = 999
        return days

    def find_all_episodes(self, options):
        premium = False
        if options.username and options.password:
            premium = self._login(options.username, options.password)
            if isinstance(premium, Exception):
                log.error(premium.message)
                return None

        jsondata = self._get_show_info()

        episodes = []
        n = 1
        for i in jsondata["results"]:
            if premium:
                text = "availability_group_premium"
            else:
                text = "availability_group_free"

            days = self._getdays(i, text)
            if premium and days == 0:
                days = self._getdays(i, "availability_group_free")

            if days > 0:
                video_id = i["id"]
                url = "http://www.tv4play.se/program/%s?video_id=%s" % (
                    i["program"]["nid"], video_id)
                episodes.append(url)
                if n == options.all_last:
                    break
                n += 1

        return episodes

    def _login(self, username, password):
        data = self.http.request("get", "https://www.tv4play.se/session/new?https=")
        url = "https://account.services.tv4play.se/authenticate"
        postdata = {"username" : username, "password": password, "https": "", "client": "web"}

        data = self.http.request("post", url, data=postdata, cookies=self.cookies)
        res = data.json()
        if "errors" in res:
            message = res["errors"][0]
            if is_py2:
                message = message.encode("utf8")
            return ServiceError(message)
        self.cookies={"JSESSIONID": res["vimond_session_token"]}

        return True


def findvid(url, data):
    parse = urlparse(url)
    if "tv4play.se" in url:
        try:
            vid = parse_qs(parse.query)["video_id"][0]
        except KeyError:
            return None
    else:
        match = re.search(r"\"vid\":\"(\d+)\",", data)
        if match:
            vid = match.group(1)
        else:
            match = re.search(r"-(\d+)$", url)
            if match:
                vid = match.group(1)
            else:
                match = re.search(r"meta content='([^']+)' property='og:video'", data)
                if match:
                    match = re.search(r"vid=(\d+)&", match.group(1))
                    if match:
                        vid = match.group(1)
                    else:
                        log.error("Can't find video id for %s", url)
                        return
                else:
                    return None
    return vid