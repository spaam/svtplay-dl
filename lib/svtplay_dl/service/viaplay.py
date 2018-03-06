# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import re
import json
import copy
import os

from svtplay_dl.utils import filenamify
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError


class Viaplay(Service, OpenGraphThumbMixin):
    supported_domains = [
        'tv3play.se', 'tv6play.se', 'tv8play.se', 'tv10play.se',
        'tv3play.no', 'tv3play.dk', 'tv6play.no', 'viasat4play.no',
        'tv3play.ee', 'tv3play.lv', 'tv3play.lt', 'tvplay.lv', 'viagame.com',
        'juicyplay.se', 'viafree.se', 'viafree.dk', 'viafree.no', 'viafree.fi',
        'play.tv3.lt', 'tv3play.tv3.ee', 'tvplay.skaties.lv'
    ]

    def _get_video_id(self, url=None):
        """
        Extract video id. It will try to avoid making an HTTP request
        if it can find the ID in the URL, but otherwise it will try
        to scrape it from the HTML document. Returns None in case it's
        unable to extract the ID at all.
        """
        if url:
            html_data = self.http.request("get", url).text
        else:
            html_data = self.get_urldata()
        html_data = self.get_urldata()
        match = re.search(r'data-video-id="([0-9]+)"', html_data)
        if match:
            return match.group(1)
        match = re.search(r'data-videoid="([0-9]+)', html_data)
        if match:
            return match.group(1)

        clips = False
        slug = None
        match = re.search('params":({.*}),"query', self.get_urldata())
        if match:
            jansson = json.loads(match.group(1))
            if "seasonNumberOrVideoId" in jansson:
                season = jansson["seasonNumberOrVideoId"]
                match = re.search("\w-(\d+)$", season)
                if match:
                    season = match.group(1)
            else:
                return False
            if "videoIdOrEpisodeNumber" in jansson:
                videp = jansson["videoIdOrEpisodeNumber"]
                match = re.search('(\w+)-(\d+)', videp)
                if match:
                    episodenr = match.group(2)
                else:
                    episodenr = videp
                    clips = True
                match = re.search('(s\w+)-(\d+)', season)
                if match:
                    season = match.group(2)
            else:
                # sometimes videoIdOrEpisodeNumber does not work.. this is a workaround
                match = re.search('(episode|avsnitt)-(\d+)', self.url)
                if match:
                    episodenr = match.group(2)
                else:
                    episodenr = season
            if "slug" in jansson:
                slug = jansson["slug"]

            if clips:
                return episodenr
            else:
                match = self._conentpage(self.get_urldata())
                if match:
                    janson = json.loads(match.group(1))
                    for i in janson["format"]["videos"].keys():
                        if "program" in janson["format"]["videos"][str(i)]:
                            for n in janson["format"]["videos"][i]["program"]:
                                if str(n["episodeNumber"]) and int(episodenr) == n["episodeNumber"] and int(season) == n["seasonNumber"]:
                                    if slug is None or slug == n["formatSlug"]:
                                        return n["id"]
                                elif n["id"] == episodenr:
                                    return episodenr

        parse = urlparse(self.url)
        match = re.search(r'/\w+/(\d+)', parse.path)
        if match:
            return match.group(1)
        match = re.search(r'iframe src="http://play.juicyplay.se[^\"]+id=(\d+)', html_data)
        if match:
            return match.group(1)
        return None

    def get(self):
        vid = self._get_video_id()
        if vid is None:
            yield ServiceError("Can't find video file for: {0}".format(self.url))
            return

        data = self. _get_video_data(vid)
        if data.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        dataj = json.loads(data.text)

        if "msg" in dataj:
            yield ServiceError(dataj["msg"])
            return

        if dataj["type"] == "live":
            self.options.live = True

        if self.options.output_auto:
            self.options.output = self.outputfilename(dataj, vid, self.options.output)

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        streams = self.http.request("get", "http://playapi.mtgx.tv/v3/videos/stream/{0}".format(vid))
        if streams.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        streamj = json.loads(streams.text)

        if "msg" in streamj:
            yield ServiceError("Can't play this because the video is either not found or geoblocked.")
            return

        if dataj["sami_path"]:
            if dataj["sami_path"].endswith("vtt"):
                subtype = "wrst"
            else:
                subtype = "sami"
            yield subtitle(copy.copy(self.options), subtype, dataj["sami_path"])
        if dataj["subtitles_webvtt"]:
            yield subtitle(copy.copy(self.options), "wrst", dataj["subtitles_webvtt"])
        if dataj["subtitles_for_hearing_impaired"]:
            if dataj["subtitles_for_hearing_impaired"].endswith("vtt"):
                subtype = "wrst"
            else:
                subtype = "sami"
            if self.options.get_all_subtitles:
                yield subtitle(copy.copy(self.options), subtype, dataj["subtitles_for_hearing_impaired"], "-SDH")
            else:
                yield subtitle(copy.copy(self.options), subtype, dataj["subtitles_for_hearing_impaired"])

        if streamj["streams"]["medium"]:
            filename = streamj["streams"]["medium"]
            if ".f4m" in filename:
                streams = hdsparse(self.options, self.http.request("get", filename, params={"hdcore": "3.7.0"}), filename)
                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
            else:
                parse = urlparse(filename)
                match = re.search("^(/[^/]+)/(.*)", parse.path)
                if not match:
                    yield ServiceError("Can't get rtmpparse info")
                    return
                filename = "{0}://{1}:{2}{3}".format(parse.scheme, parse.hostname, parse.port, match.group(1))
                path = "-y {0}".format(match.group(2))
                self.options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf {0}".format(path)
                yield RTMP(copy.copy(self.options), filename, 800)

        if streamj["streams"]["hls"]:
            streams = hlsparse(self.options, self.http.request("get", streamj["streams"]["hls"]), streamj["streams"]["hls"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]

    def find_all_episodes(self, options):
        seasons = []
        match = re.search("(sasong|sesong)-(\d+)", urlparse(self.url).path)
        if match:
            seasons.append(match.group(2))
        else:
            match = self._conentpage(self.get_urldata())
            if match:
                janson = json.loads(match.group(1))
                for i in janson["format"]["seasons"]:
                    seasons.append(i["seasonNumber"])

        episodes = self._grab_episodes(options, seasons)
        if options.all_last > 0:
            return episodes[-options.all_last:]
        return sorted(episodes)

    def _grab_episodes(self, options, seasons):
        episodes = []
        baseurl = self.url
        match = re.search("(saeson|sasong|sesong)-\d+", urlparse(self.url).path)
        if match:
            baseurl = self.url[:self.url.rfind("/")]
            baseurl = baseurl[:baseurl.rfind("/")]

        for i in seasons:
            url = "{0}/{1}-{2}".format(baseurl, self._isswe(self.url), i)
            res = self.http.get(url)
            if res:
                match = self._conentpage(res.text)
                if match:
                    janson = json.loads(match.group(1))
                    if "program" in janson["format"]["videos"][str(i)]:
                        for n in janson["format"]["videos"][str(i)]["program"]:
                            episodes = self._videos_to_list(n["sharingUrl"], n["id"], episodes)
                    if options.include_clips:
                        if "clip" in janson["format"]["videos"][str(i)]:
                            for n in janson["format"]["videos"][str(i)]["clip"]:
                                episodes = self._videos_to_list(n["sharingUrl"], n["id"], episodes)
        return episodes

    def _isswe(self, url):
        if re.search(".se$", urlparse(url).netloc):
            return "sasong"
        elif re.search(".dk$", urlparse(url).netloc):
            return "saeson"
        else:
            return "sesong"

    def _conentpage(self, data):
        return re.search('"ContentPageProgramStore":({.*}),[ ]*"ApplicationStore', data)

    def _videos_to_list(self, url, vid, episodes):
        dataj = json.loads(self._get_video_data(vid).text)
        if "msg" not in dataj:
            filename = self.outputfilename(dataj, vid, self.options.output)
            if not self.exclude2(filename) and url not in episodes:
                episodes.append(url)
        return episodes

    def _get_video_data(self, vid):
        url = "http://playapi.mtgx.tv/v3/videos/{0}".format(vid)
        self.options.other = ""
        data = self.http.request("get", url)
        return data

    def outputfilename(self, data, vid, filename):
        self.options.service = "viafree"
        if filename:
            directory = os.path.dirname(filename)
        else:
            directory = ""

        basename = self._autoname(data)
        title = "{0}-{1}-{2}".format(basename, vid, self.options.service)
        if len(directory):
            output = os.path.join(directory, title)
        else:
            output = title
        return output

    def _autoname(self, dataj):
        program = dataj["format_slug"]
        season = None
        episode = None
        title = None

        if "season" in dataj["format_position"]:
            if dataj["format_position"]["season"] > 0:
                season = dataj["format_position"]["season"]
        if season:
            if len(dataj["format_position"]["episode"]) > 0:
                episode = dataj["format_position"]["episode"]
            try:
                episode = int(episode)
            except ValueError:
                title = filenamify(episode)
                episode = None

        if dataj["type"] == "clip":
            # Removes the show name from the end of the filename
            # e.g. Showname.S0X.title instead of Showname.S07.title-showname
            match = re.search(r'(.+)-', dataj["title"])
            if match:
                title = filenamify(match.group(1))
            else:
                title = filenamify(dataj["title"])
            if "derived_from_id" in dataj:
                if dataj["derived_from_id"]:
                    parent_id = dataj["derived_from_id"]
                    parent_episode = self.http.request("get", "http://playapi.mtgx.tv/v3/videos/{0}".format(parent_id))
                    if parent_episode.status_code != 403:  # if not geoblocked
                        datajparent = json.loads(parent_episode.text)
                        if not season and datajparent["format_position"]["season"] > 0:
                            season = datajparent["format_position"]["season"]
                        if len(datajparent["format_position"]["episode"]) > 0:
                            episode = datajparent["format_position"]["episode"]

        name = filenamify(program)
        if season:
            name = "{0}.s{1:02d}".format(name, int(season))
        if episode:
            name = "{0}e{1:02d}".format(name, int(episode))
        if title:
            name = "{0}.{1}".format(name, title)

        return name
