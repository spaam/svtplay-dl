# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os
import xml.etree.ElementTree as ET
import copy
import json
import hashlib

from svtplay_dl.log import log
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import filenamify, is_py2
from svtplay_dl.utils.urllib import urlparse, urljoin, parse_qs
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Svtplay(Service, OpenGraphThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'beta.svtplay.se', 'svtflow.se']

    def get(self):
        parse = urlparse(self.url)
        if parse.netloc == "www.svtplay.se" or parse.netloc == "svtplay.se":
            if parse.path[:6] != "/video" and parse.path[:6] != "/klipp":
                yield ServiceError("This mode is not supported anymore. need the url with the video")
                return

        match = re.search("__svtplay'] = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Cant find video info.")
            return
        janson = json.loads(match.group(1))["videoTitlePage"]

        if "live" in janson["video"]:
            self.optionslive = janson["video"]["live"]

        if self.options.output_auto:
            self.options.service = "svtplay"
            self.options.output = self.outputfilename(janson, self.options.output)

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        if "subtitles" in janson["video"]:
            for i in janson["video"]["subtitles"]:
                if i["format"] == "WebSRT":
                    yield subtitle(copy.copy(self.options), "wrst", i["url"])

        if "videoReferences" in janson["video"]:
            if len(janson["video"]["videoReferences"]) == 0:
                yield ServiceError("Media doesn't have any associated videos (yet?)")
                return

            for i in janson["video"]["videoReferences"]:
                parse = urlparse(i["url"])
                query = parse_qs(parse.query)
                if i["playerType"] == "hls" or i["playerType"] == "ios":
                    streams = hlsparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                    if "alt" in query and len(query["alt"]) > 0:
                        alt = self.http.get(query["alt"][0])
                        if alt:
                            streams = hlsparse(self.options, self.http.request("get", alt.request.url), alt.request.url)
                            if streams:
                                for n in list(streams.keys()):
                                    yield streams[n]
                if i["playerType"] == "playerType" or i["playerType"] == "flash":
                    match = re.search(r"\/se\/secure\/", i["url"])
                    if not match:
                        streams = hdsparse(self.options, self.http.request("get", i["url"], params={"hdcore": "3.7.0"}), i["url"])
                        if streams:
                            for n in list(streams.keys()):
                                yield streams[n]
                        if "alt" in query and len(query["alt"]) > 0:
                            alt = self.http.get(query["alt"][0])
                            if alt:
                                streams = hdsparse(self.options, self.http.request("get", alt.request.url, params={"hdcore": "3.7.0"}), alt.request.url)
                                if streams:
                                    for n in list(streams.keys()):
                                        yield streams[n]
                if i["playerType"] == "dash264" or i["playerType"] == "dashhbbtv":
                    streams = dashparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]

                    if "alt" in query and len(query["alt"]) > 0:
                        alt = self.http.get(query["alt"][0])
                        if alt:
                            streams = dashparse(self.options, self.http.request("get", alt.request.url), alt.request.url)
                            if streams:
                                for n in list(streams.keys()):
                                    yield streams[n]

    def _last_chance(self, videos, page, maxpage=2):
        if page > maxpage:
            return videos

        res = self.http.get("http://www.svtplay.se/sista-chansen?sida=%s" % page)
        match = re.search("__svtplay'] = ({.*});", res.text)
        if not match:
            return videos

        dataj = json.loads(match.group(1))
        pages = dataj["gridPage"]["pagination"]["totalPages"]

        for i  in dataj["gridPage"]["content"]:
            videos.append(i["contentUrl"])
        page += 1
        self._last_chance(videos, page, pages)
        return videos

    def _genre(self, jansson):
        videos = []
        for i in jansson["clusterPage"]["content"]["clips"]:
            videos.append(i["contentUrl"])
        return videos

    def find_all_episodes(self, options):
        parse = urlparse(self._url)
        
        if len(parse.path) > 7 and parse.path[-7:] == "rss.xml":
            match = self.url
        else:
            match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
            if match:
                match = match.group(1)
            
        if match is None:
            videos = []
            match = re.search("__svtplay'] = ({.*});", self.get_urldata())
            if re.search("sista-chansen", parse.path):
                videos = self._last_chance(videos, 1)
            elif not match:
                log.error("Couldn't retrieve episode list")
                return
            else:
                dataj = json.loads(match.group(1))
                if re.search("/genre", parse.path):
                    videos = self._genre(dataj)
                else:
                    items = dataj["videoTitlePage"]["realatedVideosTabs"]
                    for i in items:
                        if "sasong" in i["slug"]:
                            for n in i["videos"]:
                                if n["url"] not in videos:
                                    videos.append(n["url"])
                        if "senast" in i["slug"]:
                            for n in i["videos"]:
                                if n["url"] not in videos:
                                    videos.append(n["url"])

            episodes = [urljoin("http://www.svtplay.se", x) for x in videos]
        else:
            data = self.http.request("get", match).content
            xml = ET.XML(data)

            episodes = [x.text for x in xml.findall(".//item/link")]
        episodes_new = []
        n = 1
        for i in episodes:
            episodes_new.append(i)
            if n == options.all_last:
                break
            n += 1
        return sorted(episodes_new)

    def outputfilename(self, data, filename):
        directory = os.path.dirname(filename)
        name = data["video"]["titlePagePath"]
        other = filenamify(data["video"]["title"])
        if "programVersionId" in data["video"]:
            vid = str(data["video"]["programVersionId"])
        else:
            vid = str(data["video"]["id"])
        if is_py2:
            id = hashlib.sha256(vid).hexdigest()[:7]
        else:
            id = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        season = self.seasoninfo(data)
        title = name
        if season:
            title += ".%s" % season
        if other:
            title += ".%s" % other
        title += "-%s-svtplay" % id
        title = filenamify(title)
        if len(directory):
            output = os.path.join(directory, title)
        else:
            output = title
        return output


    def seasoninfo(self, data):
        if "season" in data["video"]:
            season = data["video"]["season"]
            if season < 10:
                season = "0%s" % season
            episode = data["video"]["episodeNumber"]

            if episode < 10:
                episode = "0%s" % episode
            if int(season) == 0 and int(episode) == 0:
                return None
            return "S%sE%s" % (season, episode)
        else:
            return None
