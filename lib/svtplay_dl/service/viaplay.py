# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.log import log
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import HLS, hlsparse
from svtplay_dl.subtitle import subtitle
from svtplay_dl.error import ServiceError

class Viaplay(Service, OpenGraphThumbMixin):
    supported_domains = [
        'tv3play.se', 'tv6play.se', 'tv8play.se', 'tv10play.se',
        'tv3play.no', 'tv3play.dk', 'tv6play.no', 'viasat4play.no',
        'tv3play.ee', 'tv3play.lv', 'tv3play.lt', 'tvplay.lv', 'viagame.com',
        'juicyplay.se']

    def __init__(self, url):
        Service.__init__(self, url)
        self.subtitle = None

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

        parse = urlparse(self.url)
        match = re.search(r'/\w+/(\d+)', parse.path)
        if match:
            return match.group(1)
        match = re.search('iframe src="http://play.juicyplay.se[^\"]+id=(\d+)', html_data)
        if match:
            return match.group(1)
        return None

    def get(self, options):
        vid = self._get_video_id()
        if vid is None:
            yield ServiceError("Can't find video file for: %s" % self.url)
            return

        url = "http://playapi.mtgx.tv/v3/videos/%s" % vid
        options.other = ""
        data = self.http.request("get", url)
        if data.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        dataj = json.loads(data.text)
        if "msg" in dataj:
            yield ServiceError(dataj["msg"])
            return

        if dataj["type"] == "live":
            options.live = True

        if self.exclude(options):
            yield ServiceError("Excluding video")
            return

        if dataj["sami_path"]:
            yield subtitle(copy.copy(options), "sami", dataj["sami_path"])
        if dataj["subtitles_for_hearing_impaired"]:
            yield subtitle(copy.copy(options), "sami", dataj["subtitles_for_hearing_impaired"])

        streams = self.http.request("get", "http://playapi.mtgx.tv/v3/videos/stream/%s" % vid)
        if streams.status_code == 403:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        streamj = json.loads(streams.text)

        if "msg" in streamj:
            yield ServiceError("Can't play this because the video is either not found or geoblocked.")
            return

        if streamj["streams"]["medium"]:
            filename = streamj["streams"]["medium"]
            if ".f4m" in filename:
                streams = hdsparse(copy.copy(options), self.http.request("get", filename, params={"hdcore": "3.7.0"}).text, filename)
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
                options.other = "-W http://flvplayer.viastream.viasat.tv/flvplayer/play/swf/player.swf %s" % path
                yield RTMP(copy.copy(options), filename, 800)

        if streamj["streams"]["hls"]:
            streams = hlsparse(streamj["streams"]["hls"], self.http.request("get", streamj["streams"]["hls"]).text)
            if streams:
                for n in list(streams.keys()):
                    yield HLS(copy.copy(options), streams[n], n)

    def find_all_episodes(self, options):
        format_id = re.search(r'data-format-id="(\d+)"', self.get_urldata())
        if not format_id:
            log.error("Can't find video info for all episodes")
            return
        data = self.http.request("get", "http://playapi.mtgx.tv/v1/sections?sections=videos.one,seasons.videolist&format=%s" % format_id.group(1)).text
        jsondata = json.loads(data)
        videos = jsondata["_embedded"]["sections"][1]["_embedded"]["seasons"][0]["_embedded"]["episodelist"]["_embedded"]["videos"]

        n = 0
        episodes = []
        for i in videos:
            if n == options.all_last:
                break
            episodes.append(i["sharing"]["url"])
            n += 1
        return episodes
