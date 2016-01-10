# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os
import xml.etree.ElementTree as ET
import copy
import hashlib

from svtplay_dl.log import log
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import filenamify, ensure_unicode
from svtplay_dl.utils.urllib import urlparse, urljoin
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Svtplay(Service, OpenGraphThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'beta.svtplay.se', 'svtflow.se']

    def get(self):
        old = False

        parse = urlparse(self.url)
        if parse.netloc == "www.svtplay.se" or parse.netloc == "svtplay.se":
            if parse.path[:6] != "/video":
                yield ServiceError("This mode is not supported anymore. need the url with the video")
                return

        vid = self.find_video_id()
        if vid is None:
            yield ServiceError("Cant find video id for this video")
            return
        if re.match("^[0-9]+$", vid):
            old = True

        url = "http://www.svt.se/videoplayer-api/video/%s" % vid
        data = self.http.request("get", url)
        if data.status_code == 404:
            yield ServiceError("Can't get the json file for %s" % url)
            return

        data = data.json()
        if "live" in data:
            self.options.live = data["live"]
        if old:
            params = {"output": "json"}
            dataj = self.http.request("get", self.url, params=params).json()
        else:
            dataj = data

        if self.options.output_auto:
            self.options.service = "svtplay"
            self.options.output = self.outputfilename(dataj, self.options.output, ensure_unicode(self.get_urldata()))

        if self.exclude(self.options):
            yield ServiceError("Excluding video")
            return

        if "subtitleReferences" in data:
            for i in data["subtitleReferences"]:
                if i["format"] == "websrt":
                    yield subtitle(copy.copy(self.options), "wrst", i["url"])
        if old and dataj["video"]["subtitleReferences"]:
            try:
                suburl = dataj["video"]["subtitleReferences"][0]["url"]
            except KeyError:
                pass
            if suburl and len(suburl) > 0:
                yield subtitle(copy.copy(self.options), "wrst", suburl)

        if self.options.force_subtitle:
            return

        if len(data["videoReferences"]) == 0:
            yield ServiceError("Media doesn't have any associated videos (yet?)")
            return

        for i in data["videoReferences"]:
            if i["format"] == "hls" or i["format"] == "ios":
                streams = hlsparse(self.options, self.http.request("get", i["url"]), i["url"])
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
            if i["format"] == "hds" or i["format"] == "flash":
                match = re.search(r"\/se\/secure\/", i["url"])
                if not match:
                    streams = hdsparse(self.options, self.http.request("get", i["url"], params={"hdcore": "3.7.0"}), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]

    def find_video_id(self):
        match = re.search('data-video-id="([^"]+)"', self.get_urldata())
        if match:
            return match.group(1)
        parse = urlparse(self.url)
        match = re.search("/video/([0-9]+)/", parse.path)
        if match:
            return match.group(1)
        match = re.search("/videoEpisod-([^/]+)/", parse.path)
        if match:
            self._urldata = None
            self._url = "http://www.svtplay.se/video/%s/" % match.group(1)
            self.get_urldata()
            return self.find_video_id()
        return None

    def find_all_episodes(self, options):
        match = re.search(r'<link rel="alternate" type="application/rss\+xml" [^>]*href="([^"]+)"',
                          self.get_urldata())
        if match is None:
            match = re.findall(r'a class="play[^"]+"\s+href="(/video[^"]+)"', self.get_urldata())
            if not match:
                log.error("Couldn't retrieve episode list")
                return
            episodes = [urljoin("http://www.svtplay.se", x) for x in match]
        else:
            data = self.http.request("get", match.group(1)).content
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


    def outputfilename(self, data, filename, raw):
        directory = os.path.dirname(filename)
        if "statistics" in data:
            name = data["statistics"]["folderStructure"]
            if name.find(".") > 0:
                name = name[:name.find(".")]
            match = re.search("^arkiv-", name)
            if match:
                name = name.replace("arkiv-", "")
            name = filenamify(name.replace("-", "."))
            other = filenamify(data["context"]["title"])
            id = data["videoId"]
        else:
            name = data["programTitle"]
            if name.find(".") > 0:
                name = name[:name.find(".")]
            name = filenamify(name.replace(" - ", "."))
            other = filenamify(data["episodeTitle"])
            id = hashlib.sha256(data["programVersionId"]).hexdigest()[:7]

        if name == other:
            other = None
        season = self.seasoninfo(raw)
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
        match = re.search(r'play_video-area-aside__sub-title">([^<]+)<span', data)
        if match:
            line = match.group(1)
        else:
            match = re.search(r'data-title="([^"]+)"', data)
            if match:
                line = match.group(1)
            else:
                return None

        line = re.sub(" +", "", match.group(1)).replace('\n', '')
        match = re.search(r"(song(\d+)-)?Avsnitt(\d+)", line)
        if match:
            if match.group(2) is None:
                season = 1
            else:
                season = int(match.group(2))
            if season < 10:
                season = "0%s" % season
            episode = int(match.group(3))
            if episode < 10:
                episode = "0%s" % episode
            return "S%sE%s" % (season, episode)
        else:
            return None
