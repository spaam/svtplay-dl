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
from svtplay_dl.log import log
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
        'juicyplay.se', 'viafree.se', 'viafree.dk', 'viafree.no']

    def _get_video_id(self):
        """
        Extract video id. It will try to avoid making an HTTP request
        if it can find the ID in the URL, but otherwise it will try
        to scrape it from the HTML document. Returns None in case it's
        unable to extract the ID at all.
        """
        html_data = self.get_urldata()
        match = re.search(r'data-video-id="([0-9]+)"', html_data)
        if match:
            return match.group(1)
        match = re.search(r'data-videoid="([0-9]+)', html_data)
        if match:
            return match.group(1)

        clips = False
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

            if clips:
                return episodenr
            else:
                match = re.search('"ContentPageProgramStore":({.*}),"ApplicationStore', self.get_urldata())
                if match:
                    janson = json.loads(match.group(1))
                    for i in janson["format"]["videos"].keys():
                        for n in janson["format"]["videos"][i]["program"]:
                            if str(n["episodeNumber"]) and int(episodenr) == n["episodeNumber"] and int(season) == n["seasonNumber"]:
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
            yield ServiceError("Can't find video file for: %s" % self.url)
            return

        url = "http://playapi.mtgx.tv/v3/videos/%s" % vid
        self.options.other = ""
        data = self.http.request("get", url)
        if data.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        dataj = json.loads(data.text)
        if "msg" in dataj:
            yield ServiceError(dataj["msg"])
            return

        if dataj["type"] == "live":
            self.options.live = True

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        streams = self.http.request("get", "http://playapi.mtgx.tv/v3/videos/stream/%s" % vid)
        if streams.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        streamj = json.loads(streams.text)

        if "msg" in streamj:
            yield ServiceError("Can't play this because the video is either not found or geoblocked.")
            return

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            self.options.service = "tv3play"
            basename = self._autoname(dataj)
            title = "%s-%s-%s" % (basename, vid, self.options.service)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if dataj["sami_path"]:
            yield subtitle(copy.copy(self.options), "sami", dataj["sami_path"])
        if dataj["subtitles_for_hearing_impaired"]:
            yield subtitle(copy.copy(self.options), "sami", dataj["subtitles_for_hearing_impaired"])

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
                filename = "%s://%s:%s%s" % (parse.scheme, parse.hostname, parse.port, match.group(1))
                path = "-y %s" % match.group(2)
                self.options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf %s" % path
                yield RTMP(copy.copy(self.options), filename, 800)

        if streamj["streams"]["hls"]:
            streams = hlsparse(self.options, self.http.request("get", streamj["streams"]["hls"]), streamj["streams"]["hls"])
            if streams:
                for n in list(streams.keys()):
                    yield streams[n]

    def find_all_episodes(self, options):
        videos = []
        match = re.search('"ContentPageProgramStore":({.*}),"ApplicationStore', self.get_urldata())
        if match:
            janson = json.loads(match.group(1))
            seasons = []
            for i in janson["format"]["seasons"]:
                seasons.append(i["seasonNumber"])
            for i in seasons:
                for n in janson["format"]["videos"][str(i)]["program"]:
                    videos.append(n["sharingUrl"])

        n = 0
        episodes = []
        for i in videos:
            if n == options.all_last:
                break
            episodes.append(i)
            n += 1
        return episodes

    def _autoname(self, dataj):
        program = dataj["format_slug"]
        season = dataj["format_position"]["season"]
        episode = None
        if season:
            if len(dataj["format_position"]["episode"]) > 0:
                episode = dataj["format_position"]["episode"]
        name = filenamify(program)
        if season:
            name = "%s.s%s" % (name, season)
        if episode:
            name = "%se%s" % (name, episode)
        return name