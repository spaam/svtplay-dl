# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.error import ServiceError


class Vidme(Service, OpenGraphThumbMixin):
    supported_domains = ['vid.me']

    def get(self):
        parse = urlparse(self.url)
        if parse.netloc is not "vid.me":
            yield ServiceError("Need the url with the video")
        vid = parse.path[1:]
        res = self.http.get("https://api.vid.me/videoByUrl/{0}".format(vid))
        try:
            janson = res.json()
        except ValueError:
            yield ServiceError("Can't decode api request: {0}".format(res.request.url))
            return
        videos = self._get_video(janson)
        for i in videos:
            yield i

    def _get_video(self, janson):

        if "video" in janson and "formats" in janson["video"]:
            janson_v = janson["video"]
            if len(janson_v["formats"]) == 0:
                yield ServiceError("Media doesn't have any associated videos.")
                return

            for i in janson_v["formats"]:
                streams = None

                if i["type"] == "hls":
                    streams = hlsparse(self.options, self.http.request("get", i["uri"]), i["uri"])

                elif i["type"] == "dash":
                    streams = dashparse(self.options, self.http.request("get", i["uri"]), i["uri"])

                if streams:
                    for n in list(streams.keys()):
                        yield streams[n]
