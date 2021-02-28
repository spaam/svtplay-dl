import copy
import json
import logging
import re
import uuid

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


class Dr(Service, OpenGraphThumbMixin):
    supported_domains = ["dr.dk"]

    def get(self):
        data = self.get_urldata()

        match = re.search("__data = ([^<]+)</script>", data)
        if not match:
            yield ServiceError("Cant find info for this video")
            return
        janson = json.loads(match.group(1))
        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
        offers = page["entries"][0]["item"]["offers"]
        resolution = None
        vid = None
        for i in offers:
            if i["deliveryType"] == "Stream":
                vid = i["scopes"][0]
                resolution = i["resolution"]

        deviceid = uuid.uuid1()
        res = self.http.request(
            "post",
            "https://isl.dr-massive.com/api/authorization/anonymous-sso?device=web_browser&ff=idp%2Cldp&lang=da",
            json={"deviceId": str(deviceid), "scopes": ["Catalog"], "optout": True},
        )
        token = res.json()[0]["value"]

        url = "https://isl.dr-massive.com/api/account/items/{}/videos?delivery=stream&device=web_browser&ff=idp%2Cldp&lang=da&resolution={}&sub=Anonymous".format(
            vid,
            resolution,
        )
        res = self.http.request("get", url, headers={"authorization": f"Bearer {token}"})
        for video in res.json():
            if video["accessService"] == "StandardVideo":
                if video["format"] == "video/hls":
                    res = self.http.request("get", video["url"])
                    if res.status_code > 400:
                        yield ServiceError("Can't play this because the video is geoblocked or not available.")
                    else:
                        streams = hlsparse(self.config, res, video["url"], output=self.output)
                        for n in list(streams.keys()):
                            yield streams[n]
                        yield subtitle(copy.copy(self.config), "wrst", video["subtitles"][0]["link"], output=self.output)

    def find_all_episodes(self, config):
        episodes = []
        data = self.get_urldata()
        match = re.search("__data = ([^<]+)</script>", data)
        if not match:
            logging.error("Can't find video info.")
            return episodes
        janson = json.loads(match.group(1))
        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
        item = page["entries"][0]["item"]
        if "season" in item:
            entries = item["season"]["episodes"]["items"]
            for i in entries:
                episodes.append("https://www.dr.dk/drtv{}".format(i["watchPath"]))

            if config.get("all_last") != -1:
                episodes = episodes[: config.get("all_last")]
            else:
                episodes.reverse()
        return episodes
