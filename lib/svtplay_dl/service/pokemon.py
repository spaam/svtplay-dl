from __future__ import absolute_import
import re
import os

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.utils import filenamify
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Pokemon(Service, OpenGraphThumbMixin):
    supported_domains = ['pokemon.com']

    def get(self):
        data = self.get_urldata()

        parse = urlparse(self.url)
        match = re.search(r'^/([a-z]{2})/', parse.path)
        if not match:
            yield ServiceError("Cant county code")
            return

        res = self.http.get("http://www.pokemon.com/api/pokemontv/channels?region=%s" % match.group(1))
        janson = res.json()
        match = re.search('data-video-season="([0-9]+)"', data)
        season = match.group(1)
        match = re.search('data-video-episode="([0-9]+)"', data)
        episode = match.group(1)

        for i in janson:
            for n in i["media"]:
                if season == n["season"] and episode == n["episode"]:
                    stream = n["stream_url"]

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            basename = os.path.basename(self.options.output)
            title = "pokemon.s%se%s-%s" % (season, episode, basename)
            title = filenamify(title)
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        streams = hlsparse(self.options, self.http.request("get", stream), stream)
        for n in list(streams.keys()):
            yield streams[n]
