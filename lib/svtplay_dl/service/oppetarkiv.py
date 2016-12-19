# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy
import os
import hashlib
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.error import ServiceError
from svtplay_dl.log import log
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.utils import ensure_unicode, filenamify, is_py2
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.urllib import urlparse, parse_qs


class OppetArkiv(Service, OpenGraphThumbMixin):
    supported_domains = ['oppetarkiv.se']

    def get(self):
        vid = self.find_video_id()
        if vid is None:
            yield ServiceError("Cant find video id for this video")
            return

        url = "http://api.svt.se/videoplayer-api/video/%s" % vid
        data = self.http.request("get", url)
        if data.status_code == 404:
            yield ServiceError("Can't get the json file for %s" % url)
            return

        data = data.json()
        if "live" in data:
            self.options.live = data["live"]

        if self.options.output_auto:
            self.options.service = "svtplay"
            self.options.output = self.outputfilename(data, self.options.output, ensure_unicode(self.get_urldata()))

        if self.exclude():
            yield ServiceError("Excluding video")
            return
        if "subtitleReferences" in data:
            for i in data["subtitleReferences"]:
                if i["format"] == "websrt":
                    yield subtitle(copy.copy(self.options), "wrst", i["url"])

        if len(data["videoReferences"]) == 0:
            yield ServiceError("Media doesn't have any associated videos (yet?)")
            return

        for i in data["videoReferences"]:
            parse = urlparse(i["url"])
            query = parse_qs(parse.query)
            if i["format"] == "hls" or i["format"] == "ios":
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
            if i["format"] == "hds" or i["format"] == "flash":
                match = re.search(r"\/se\/secure\/", i["url"])
                if not match:
                    streams = hdsparse(self.options, self.http.request("get", i["url"], params={"hdcore": "3.7.0"}),
                                       i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                    if "alt" in query and len(query["alt"]) > 0:
                        alt = self.http.get(query["alt"][0])
                        if alt:
                            streams = hdsparse(self.options,
                                               self.http.request("get", alt.request.url, params={"hdcore": "3.7.0"}),
                                               alt.request.url)
                            if streams:
                                for n in list(streams.keys()):
                                    yield streams[n]
            if i["format"] == "dash264" or i["format"] == "dashhbbtv":
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

    def find_video_id(self):
        match = re.search('data-video-id="([^"]+)"', self.get_urldata())
        if match:
            return match.group(1)
        return None

    def find_all_episodes(self, options):
        page = 1
        data = self.get_urldata()
        match = re.search(r'"/etikett/titel/([^"/]+)', data)
        if match is None:
            match = re.search(r'"http://www.oppetarkiv.se/etikett/titel/([^/]+)/', self.url)
            if match is None:
                log.error("Couldn't find title")
                return
        program = match.group(1)
        episodes = []

        n = 0
        if self.options.all_last > 0:
            sort = "tid_fallande"
        else:
            sort = "tid_stigande"

        while True:
            url = "http://www.oppetarkiv.se/etikett/titel/%s/?sida=%s&sort=%s&embed=true" % (program, page, sort)
            data = self.http.request("get", url)
            if data.status_code == 404:
                break

            data = data.text
            regex = re.compile(r'href="(/video/[^"]+)"')
            for match in regex.finditer(data):
                if n == self.options.all_last:
                    break
                episodes.append("http://www.oppetarkiv.se%s" % match.group(1))
                n += 1
            page += 1

        return episodes


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
            if not name:
                match = re.search('data-title="([^"]+)"', raw)
                if match:
                    name = filenamify(match.group(1).replace(" - ", "."))
                other = None
            else:
                if name.find(".") > 0:
                    name = name[:name.find(".")]
                name = filenamify(name.replace(" - ", "."))
                other = filenamify(data["episodeTitle"])
            if is_py2:
                id = hashlib.sha256(data["programVersionId"]).hexdigest()[:7]
            else:
                id = hashlib.sha256(data["programVersionId"].encode("utf-8")).hexdigest()[:7]

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
            season = "{:02d}".format(season)
            episode = "{:02d}".format(int(match.group(3)))
            return "S%sE%s" % (season, episode)
        else:
            return None