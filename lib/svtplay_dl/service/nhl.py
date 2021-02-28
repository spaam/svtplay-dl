import json
import re
from urllib.parse import urljoin

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class NHL(Service, OpenGraphThumbMixin):
    supported_domains = ["nhl.com"]

    def get(self):
        match = re.search(r"var initialMedia\s+= ({[^;]+);", self.get_urldata())
        if not match:
            yield ServiceError("Cant find any media on that page")
            return
        janson = json.loads(match.group(1))
        vid = janson["content_id"]
        if not janson["metaData"]:
            yield ServiceError("Can't find video on that page")
            return
        if "playbacks" in janson["metaData"]:
            for i in janson["metaData"]["playbacks"]:
                if "CLOUD" in i["name"]:
                    streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
        else:
            match = re.search(r"var mediaConfig\s+= ({[^;]+);", self.get_urldata())
            if not match:
                yield ServiceError("Cant find any media on that page")
                return
            janson = json.loads(match.group(1))
            try:
                apiurl = janson["vpm"]["mediaFramework"]["mediaFrameworkDomain"]
            except KeyError:
                yield ServiceError("Can't find api url")
                return
            filename = "{}?contentId={}&playbackScenario=HTTP_CLOUD_WIRED_WEB&format=json&platform=WEB_MEDIAPLAYER" "&_=1487455224334".format(
                janson["vpm"]["mediaFramework"]["mediaFrameworkEndPoint"],
                vid,
            )
            url = urljoin(apiurl, filename)
            res = self.http.get(url)
            janson = res.json()
            for i in janson["user_verified_event"][0]["user_verified_content"][0]["user_verified_media_item"]:
                streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]
