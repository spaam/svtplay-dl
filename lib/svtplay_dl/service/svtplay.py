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
                yield ServiceError("This mode is not supported anymore. Need the url with the video.")
                return

        query = parse_qs(parse.query)
        self.access = None
        if "accessService" in query:
            self.access = query["accessService"]

        match = re.search("__svtplay'] = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video info.")
            return
        janson = json.loads(match.group(1))["videoPage"]

        if "programTitle" not in janson["video"]:
            yield ServiceError("Can't find any video on that page.")
            return

        if self.access:
            for i in janson["video"]["versions"]:
                if i["accessService"] == self.access:
                    url = urljoin("http://www.svtplay.se", i["contentUrl"])
                    res = self.http.get(url)
                    match = re.search("__svtplay'] = ({.*});", res.text)
                    if not match:
                        yield ServiceError("Can't find video info.")
                        return
                    janson = json.loads(match.group(1))["videoPage"]

        if "live" in janson["video"]:
            self.options.live = janson["video"]["live"]

        if self.options.output_auto:
            self.options.service = "svtplay"
            self.options.output = self.outputfilename(janson["video"], self.options.output)

        if self.exclude():
            yield ServiceError("Excluding video.")
            return

        if "programVersionId" in janson["video"]:
            vid = janson["video"]["programVersionId"]
        else:
            vid = janson["video"]["id"]
        res = self.http.get("http://api.svt.se/videoplayer-api/video/{0}".format(vid))
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {0}".format(res.request.url))
            return
        videos = self._get_video(janson)
        for i in videos:
            yield i

    def _get_video(self, janson):
        if "live" in janson:
            self.options.live = janson["live"]
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if i["format"] == "websrt" and "url" in i:
                    yield subtitle(copy.copy(self.options), "wrst", i["url"])

        if "videoReferences" in janson:
            if len(janson["videoReferences"]) == 0:
                yield ServiceError("Media doesn't have any associated videos.")
                return

            for i in janson["videoReferences"]:
                streams = None
                alt_streams = None
                alt = None
                query = parse_qs(urlparse(i["url"]).query)
                if "alt" in query and len(query["alt"]) > 0:
                    alt = self.http.get(query["alt"][0])

                if i["format"] == "hls":
                    streams = hlsparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if alt:
                        alt_streams = hlsparse(self.options, self.http.request("get", alt.request.url), alt.request.url)

                elif i["format"] == "hds":
                    match = re.search(r"\/se\/secure\/", i["url"])
                    if not match:
                        streams = hdsparse(self.options, self.http.request("get", i["url"], params={"hdcore": "3.7.0"}), i["url"])
                        if alt:
                            alt_streams = hdsparse(self.options, self.http.request("get", alt.request.url, params={"hdcore": "3.7.0"}), alt.request.url)
                elif i["format"] == "dash264" or i["format"] == "dashhbbtv":
                    streams = dashparse(self.options, self.http.request("get", i["url"]), i["url"])
                    if alt:
                        alt_streams = dashparse(self.options, self.http.request("get", alt.request.url), alt.request.url)

                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
                if alt_streams:
                    for n in list(alt_streams.keys()):
                        yield alt_streams[n]

    def _last_chance(self, videos, page, maxpage=2):
        if page > maxpage:
            return videos

        res = self.http.get("http://www.svtplay.se/sista-chansen?sida={}".format(page))
        match = re.search("__svtplay'] = ({.*});", res.text)
        if not match:
            return videos

        dataj = json.loads(match.group(1))
        pages = dataj["gridPage"]["pagination"]["totalPages"]

        for i in dataj["gridPage"]["content"]:
            videos.append(i["contentUrl"])
        page += 1
        self._last_chance(videos, page, pages)
        return videos

    def _genre(self, jansson):
        videos = []
        parse = urlparse(self._url)
        dataj = jansson["clusterPage"]
        tab = re.search("tab=(.+)", parse.query)
        if tab:
            tab = tab.group(1)
            for i in dataj["tabs"]:
                if i["slug"] == tab:
                    videos = self.videos_to_list(i["content"], videos)
        else:
            videos = self.videos_to_list(dataj["clips"], videos)

        return videos

    def find_all_episodes(self, options):
        parse = urlparse(self._url)
        
        if len(parse.path) > 7 and parse.path[-7:] == "rss.xml":
            rss_url = self.url
        else:
            rss_url = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"', self.get_urldata())
            if rss_url: 
                rss_url = rss_url.group(1)

        valid_rss = False
        tab = None
        if parse.query:
            match = re.search("tab=(.+)", parse.query)
            if match:
                tab = match.group(1)

        #Clips and tab can not be used with RSS-feed
        if rss_url and not self.options.include_clips and not tab:
            rss_data = self.http.request("get", rss_url).content

            try:
                xml = ET.XML(rss_data)
                episodes = [x.text for x in xml.findall(".//item/link")]
                #TODO add better checks for valid RSS-feed here
                valid_rss = True
            except ET.ParseError:
                log.info("Error parsing RSS-feed at %s, make sure it is a valid RSS-feed, will use other method to find episodes." % rss_url)
        else:
            #if either tab or include_clips is set remove rss.xml from url if set manually. 
            if len(parse.path) > 7 and parse.path[-7:] == "rss.xml":                
                self._url = self.url.replace("rss.xml","")

        if not valid_rss:
            videos = []
            tab = None
            match = re.search("__svtplay'] = ({.*});", self.get_urldata())
            if re.search("sista-chansen", parse.path):
                videos = self._last_chance(videos, 1)
            elif not match:
                log.error("Couldn't retrieve episode list.")
                return
            else:
                dataj = json.loads(match.group(1))
                if re.search("/genre", parse.path):
                    videos = self._genre(dataj)
                else:
                    if parse.query:
                        match = re.search("tab=(.+)", parse.query)
                        if match:
                            tab = match.group(1)
                            
                    items = dataj["relatedVideoContent"]["relatedVideosAccordion"]
                    for i in items:
                        if tab:
                            if i["slug"] == tab:
                                videos = self.videos_to_list(i["videos"], videos)
                        else:
                            if "klipp" not in i["slug"] and "kommande" not in i["slug"]:
                                videos = self.videos_to_list(i["videos"], videos)
                        if self.options.include_clips: 
                            if i["slug"] == "klipp":
                                videos = self.videos_to_list(i["videos"], videos)

            episodes = [urljoin("http://www.svtplay.se", x) for x in videos]

        if options.all_last > 0:
            return sorted(episodes)[-options.all_last:]
        return sorted(episodes)

    def videos_to_list(self, lvideos, videos):
        for n in lvideos:
            parse = urlparse(n["contentUrl"])
            if parse.path not in videos:
                filename = self.outputfilename(n, self.options.output)
                if not self.exclude2(filename):
                    videos.append(parse.path)
            if "versions" in n:
                for i in n["versions"]:
                    parse = urlparse(i["contentUrl"])
                    filename = "" # output is None here.
                    if "accessService" in i:
                        if i["accessService"] == "audioDescription":
                            filename += "-syntolkat"
                        if i["accessService"] == "signInterpretation":
                            filename += "-teckentolkat"
                    if not self.exclude2(filename) and parse.path not in videos:
                        videos.append(parse.path)

        return videos

    def outputfilename(self, data, filename):
        if filename:
            directory = os.path.dirname(filename)
        else:
            directory = ""
        name = None
        if data["programTitle"]:
            name = filenamify(data["programTitle"])
        other = filenamify(data["title"])

        if "programVersionId" in data:
            vid = str(data["programVersionId"])
        else:
            vid = str(data["id"])
        if is_py2:
            id = hashlib.sha256(vid).hexdigest()[:7]
        else:
            id = hashlib.sha256(vid.encode("utf-8")).hexdigest()[:7]

        if name == other:
            other = None
        elif name is None:
            name = other
            other = None
        season = self.seasoninfo(data)
        title = name
        if season:
            title += ".{}".format(season)
        if other:
            title += ".{}".format(other)
        if "accessService" in data:
            if data["accessService"] == "audioDescription":
                title += "-syntolkat"
            if data["accessService"] == "signInterpretation":
                title += "-teckentolkat"
        title += "-{}-svtplay".format(id)
        title = filenamify(title)
        if len(directory):
            output = os.path.join(directory, title)
        else:
            output = title
        return output

    def seasoninfo(self, data):
        if "season" in data and data["season"]:
            season = "{:02d}".format(data["season"])
            episode = "{:02d}".format(data["episodeNumber"])
            if int(season) == 0 and int(episode) == 0:
                return None
            return "S{}E{}".format(season, episode)
        else:
            return None
