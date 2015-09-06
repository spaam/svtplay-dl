# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os
import xml.etree.ElementTree as ET
import copy
from  svtplay_dl.log import log
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils import filenamify, ensure_unicode
from svtplay_dl.utils.urllib import urlparse, urljoin
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError

class Svtplay(Service, OpenGraphThumbMixin):
    supported_domains = ['svtplay.se', 'svt.se', 'beta.svtplay.se', 'svtflow.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

    def get(self, options):
        if re.findall("svt.se", self.url):
            data = self.get_urldata()
            match = re.search(r"data-json-href=\"(.*)\"", data)
            if match:
                filename = match.group(1).replace("&amp;", "&").replace("&format=json", "")
                url = "http://www.svt.se%s" % filename
            else:
                yield ServiceError("Can't find video file for: %s" % self.url)
                return
        else:
            url = self.url

        pos = url.find("?")
        if pos < 0:
            if "svt.se" in url:
                dataurl = "%s?format=json" % url
            else:
                dataurl = "%s?output=json" % url
        else:
            if "svt.se" in url:
                dataurl = "%s&format=json" % url
            else:
                dataurl = "%s&output=json" % url
        data = self.http.request("get", dataurl)
        if data.status_code == 404:
            yield ServiceError("Can't get the json file for %s" % self.json)
            return
        data = data.json()
        if "live" in data["video"]:
            options.live = data["video"]["live"]

        if options.output_auto:
            options.service = "svtplay"
            options.output = outputfilename(data, options.output, ensure_unicode(self.get_urldata()))

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        if data["video"]["subtitleReferences"]:
            try:
                suburl = data["video"]["subtitleReferences"][0]["url"]
            except KeyError:
                pass
            if suburl and len(suburl) > 0:
                yield subtitle(copy.copy(options), "wrst", suburl)

        if options.force_subtitle:
            return

        for i in data["video"]["videoReferences"]:
            parse = urlparse(i["url"])

            if parse.path.find("m3u8") > 0:
                streams = hlsparse(i["url"], self.http.request("get", i["url"]).text)
                if streams:
                    for n in list(streams.keys()):
                        yield HLS(copy.copy(options), streams[n], n)
            elif parse.path.find("f4m") > 0:
                match = re.search(r"\/se\/secure\/", i["url"])
                if not match:
                    res = self.http.request("get", i["url"], params={"hdcore": "3.7.0"})
                    streams = hdsparse(copy.copy(options), res.text, i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
            elif parse.scheme == "rtmp":
                embedurl = "%s?type=embed" % url
                data = self.http.request("get", embedurl).text
                match = re.search(r"value=\"(/(public)?(statiskt)?/swf(/video)?/svtplayer-[0-9\.a-f]+swf)\"", data)
                swf = "http://www.svtplay.se%s" % match.group(1)
                options.other = "-W %s" % swf
                yield RTMP(copy.copy(options), i["url"], i["bitrate"])
            else:
                yield HTTP(copy.copy(options), i["url"], "0")

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


def outputfilename(data, filename, raw):
    directory = os.path.dirname(filename)
    name = data["statistics"]["folderStructure"]
    if name.find(".") > 0:
        name = name[:name.find(".")]
    match = re.search("^arkiv-", name)
    if match:
        name = name.replace("arkiv-", "")
    name = name.replace("-", ".")
    season = seasoninfo(raw)
    other = filenamify(data["context"]["title"])
    if season:
        title = "%s.%s.%s-%s-svtplay" % (name, season, other, data["videoId"])
    else:
        title = "%s.%s-%s-svtplay" % (name, other, data["videoId"])
    title = filenamify(title)
    if len(directory):
        output = os.path.join(directory, title)
    else:
        output = title
    return output


def seasoninfo(data):
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
