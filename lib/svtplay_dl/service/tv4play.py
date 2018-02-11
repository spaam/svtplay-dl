# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals
import re
import os
import xml.etree.ElementTree as ET
import json
import copy
from datetime import datetime, timedelta

from svtplay_dl.utils.urllib import urlparse, parse_qs, quote_plus
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import is_py2_old, is_py2, filenamify
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ['tv4play.se', 'tv4.se']

    def get(self):

        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":

            end_time_stamp = (datetime.utcnow() - timedelta(seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = "https://bbr-l2v.akamaized.net/live/{0}/master.m3u8?in={1}&out={2}?".format(parse.path[9:],
                                                                                              start_time_stamp.isoformat(),
                                                                                              end_time_stamp.isoformat())

            self.options.live = True
            self.options.hls_time_stamp = True
            streams = hlsparse(self.options, self.http.request("get", url), url)
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]
            return

        data = self.get_urldata()

        vid = findvid(self.url, data)
        if not vid:
            yield ServiceError("Can't find video id for {0}.".format(self.url))
            return

        url = "http://prima.tv4play.se/api/web/asset/{0}/play".format(vid)
        data = self.http.request("get", url, cookies=self.cookies)
        if data.status_code == 401:
            xml = ET.XML(data.content)
            code = xml.find("code").text
            if code == "SESSION_NOT_AUTHENTICATED":
                yield ServiceError("Can't access premium content")
            elif code == "ASSET_PLAYBACK_INVALID_GEO_LOCATION":
                yield ServiceError("Can't download this video because of geoblock.")
            else:
                yield ServiceError("Can't find any info for that video.")
            return
        if data.status_code == 404:
            yield ServiceError("Can't find the video api.")
            return
        xml = ET.XML(data.content)
        ss = xml.find("items")
        if is_py2_old:
            sa = list(ss.getiterator("item"))
        else:
            sa = list(ss.iter("item"))

        if xml.find("live").text:
            self.options.live = (xml.find("live").text != "false")
        if xml.find("drmProtected").text == "true":
            yield ServiceError("We can't download DRM protected content from this site.")
            return
        if xml.find("playbackStatus").text == "NOT_STARTED":
            yield ServiceError("Can't download something that is not started.")
            return

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "tv4play"
            basename = self._autoname(vid)
            if not basename:
                yield ServiceError("Cant find vid id for autonaming.")
                return
            title = "{0}-{1}-{2}".format(basename, vid, self.options.service)
            title = filenamify(title)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video.")
            return

        for i in sa:
            if i.find("mediaFormat").text == "mp4":
                base = urlparse(i.find("base").text)
                parse = urlparse(i.find("url").text)
                if "rtmp" in base.scheme:
                    swf = "http://www.tv4play.se/flash/tv4playflashlets.swf"
                    self.options.other = "-W {0} -y {1}".format(swf, i.find("url").text)
                    yield RTMP(copy.copy(self.options), i.find("base").text, i.find("bitrate").text)
                elif parse.path[len(parse.path) - 3:len(parse.path)] == "f4m":
                    streams = hdsparse(self.options, self.http.request("get", i.find("url").text,
                                                                       params={"hdcore": "3.7.0"}), i.find("url").text)
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
            elif i.find("mediaFormat").text == "webvtt":
                yield subtitle(copy.copy(self.options), "wrst", i.find("url").text)

        url = "https://prima.tv4play.se/api/web/asset/{0}/play?protocol=hls3".format(vid)
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
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]

    def _get_show_info(self):
        show = self._get_showname()
        live = str(self.options.live).lower()
        data = self.http.request("get", "http://webapi.tv4play.se/play/video_assets?type=episode&is_live={0}&platform=web&node_nids={1}&per_page=99999".format(live, show)).text
        jsondata = json.loads(data)
        return jsondata

    def _get_clip_info(self, vid):
        show = self._get_showname()
        page = 1
        assets = page * 1000
        run = True
        live = str(self.options.live).lower()
        while run:
            data = self.http.request("get", "http://webapi.tv4play.se/play/video_assets?type=clips&is_live={0}&platform=web&node_nids={1}&per_page=1000&page={2}".format(live, show, page)).text
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

    def _get_showname(self):
        parse = urlparse(self.url)
        show = None
        if parse.path.count("/") > 2:
            match = re.search("^/([^/]+)/", parse.path)
            if "program" == match.group(1):
                match = re.search("^/program/([^/]+)/", parse.path)
                if match:
                    show = match.group(1)
            else:
                show = match.group(1)
        else:
            show = parse.path[parse.path.find("/", 1) + 1:]
        if show and not re.search("%", show):
            if is_py2 and isinstance(show, unicode):
                show = show.encode("utf-8")
            show = quote_plus(show)
        return show

    def _seasoninfo(self, data):
        if "season" in data and data["season"]:
            season = "{:02d}".format(data["season"])
            if "episode" in data:
                episode = "{:02d}".format(data["episode"])
                if int(season) == 0 and int(episode) == 0:
                    return None
                return "s{0}e{1}".format(season, episode)
            else:
                return "s{0}".format(season)
        else:
            return None

    def _autoname(self, vid):
        jsondata = self._get_show_info()
        for i in jsondata["results"]:
            if vid == i["id"]:
                season = self._seasoninfo(i)
                if season:
                    index = len(i["program"]["name"])
                    return "{0}.{1}{2}".format(i["title"][:index], season, i["title"][index:])
                return i["title"]

        aname = self._get_clip_info(vid)
        if aname is not None:
            return aname

        aname = self._get_showname()
        if aname is not None:
            return aname

        return "tv4Stream"

    def _getdays(self, data, text):
        try:
            days = int(data["availability"][text])
        except (ValueError, TypeError):
            days = 999
        return days

    def find_all_episodes(self, options):
        premium = False
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
                url = "http://www.tv4play.se/program/{0}?video_id={1}"\
                    .format(i["program"]["nid"], video_id)
                episodes.append(url)
                if n == options.all_last:
                    break
                n += 1

        return episodes


def findvid(url, data):
    parse = urlparse(url)
    if "tv4play.se" in url:
        if "video_id" in parse_qs(parse.query):
            return parse_qs(parse.query)["video_id"][0]
        match = re.search(r'burtVmanId: "(\d+)"', data)
        if match:
            return match.group(1)
    else:
        match = re.search(r"\"vid\":\"(\d+)\",", data)
        if match:
            return match.group(1)
        match = re.search(r"-(\d+)$", url)
        if match:
            return match.group(1)
        match = re.search(r"meta content='([^']+)' property='og:video'", data)
        if match:
            match = re.search(r"vid=(\d+)&", match.group(1))
            if match:
                return match.group(1)
    return None
