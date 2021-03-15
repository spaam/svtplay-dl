# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service
from svtplay_dl.utils.text import decode_html_entities


class Aftonbladettv(Service):
    supported_domains = ["svd.se", "tv.aftonbladet.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search('data-player-config="([^"]+)"', data)
        if not match:
            match = re.search('data-svpPlayer-video="([^"]+)"', data)
            if not match:
                match = re.search("window.ASSET = ({.*})", data)
                if not match:
                    yield ServiceError("Can't find video info")
                    return
        data = json.loads(decode_html_entities(match.group(1)))
        streams = hlsparse(self.config, self.http.request("get", data["streamUrls"]["hls"]), data["streamUrls"]["hls"], output=self.output)
        for n in list(streams.keys()):
            yield streams[n]


class Aftonbladet(Service):
    supported_domains = ["aftonbladet.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search("window.FLUX_STATE = ({.*})</script>", data)
        if not match:
            yield ServiceError("Can't find video info")
            return

        try:
            janson = json.loads(match.group(1))
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {}".format(match.group(1)))
            return

        videos = self._get_video(janson)
        yield from videos

    def _get_video(self, janson):
        collections = janson["collections"]
        for n in list(collections.keys()):
            contents = collections[n]["contents"]["items"]
            for i in list(contents.keys()):
                if "type" in contents[i] and contents[i]["type"] == "video":
                    streams = hlsparse(
                        self.config,
                        self.http.request("get", contents[i]["videoAsset"]["streamUrls"]["hls"]),
                        contents[i]["videoAsset"]["streamUrls"]["hls"],
                        output=self.output,
                    )
                    for key in list(streams.keys()):
                        yield streams[key]
