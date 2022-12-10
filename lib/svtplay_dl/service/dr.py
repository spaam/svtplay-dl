import copy
import json
import logging
import re
import uuid
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe


class Dr(Service, OpenGraphThumbMixin):
    supported_domains = ["dr.dk"]

    def get(self):
        data = self.get_urldata()

        match = re.search("__data = ([^<]+)</script>", data)
        if not match:
            match = re.search('source src="([^"]+)"', data)
            if not match:
                yield ServiceError("Cant find info for this video")
                return

            res = self.http.request("get", match.group(1))
            if res.status_code > 400:
                yield ServiceError("Can't play this because the video is geoblocked or not available.")
            else:
                yield from hlsparse(self.config, res, match.group(1), output=self.output)
            return
        janson = json.loads(match.group(1))
        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
        resolution = None
        vid = None
        if "item" in page["entries"][0]:
            offers = page["entries"][0]["item"]["offers"]
        elif "item" in page:
            offers = page["item"]["offers"]

        offerlist = []
        for i in offers:
            if i["deliveryType"] == "Stream":
                offerlist.append([i["scopes"][0], i["resolution"]])

        deviceid = uuid.uuid1()
        res = self.http.request(
            "post",
            "https://isl.dr-massive.com/api/authorization/anonymous-sso?device=web_browser&ff=idp%2Cldp&lang=da",
            json={"deviceId": str(deviceid), "scopes": ["Catalog"], "optout": True},
        )
        token = res.json()[0]["value"]

        if len(offerlist) == 0:
            yield ServiceError("Can't find any videos")
            return

        for i in offerlist:
            vid, resolution = i
            url = (
                f"https://isl.dr-massive.com/api/account/items/{vid}/videos?delivery=stream&device=web_browser&"
                f"ff=idp%2Cldp&lang=da&resolution={resolution}&sub=Anonymous"
            )
            res = self.http.request("get", url, headers={"authorization": f"Bearer {token}"})
            for video in res.json():
                if video["accessService"] == "StandardVideo" and video["format"] == "video/hls":
                    res = self.http.request("get", video["url"])
                    if res.status_code > 400:
                        yield ServiceError("Can't play this because the video is geoblocked or not available.")
                    else:
                        logging.info("suuubu")
                        yield from hlsparse(self.config, res, video["url"], output=self.output)
                        if len(video["subtitles"]) > 0:
                            yield from subtitle_probe(copy.copy(self.config), video["subtitles"][0]["link"], output=self.output)

    def find_all_episodes(self, config):
        episodes = []
        seasons = []
        data = self.get_urldata()
        match = re.search("__data = ([^<]+)</script>", data)
        if not match:
            if "bonanza" in self.url:
                parse = urlparse(self.url)
                match = re.search(r"(\/bonanza\/serie\/[0-9]+\/[\-\w]+)", parse.path)
                if match:
                    match = re.findall(rf"a href=\"({match.group(1)}\/\d+[^\"]+)\"", data)
                    if not match:
                        logging.error("Can't find video info.")
                    for url in match:
                        episodes.append(f"https://www.dr.dk{url}")
                else:
                    logging.error("Can't find video info.")
                return episodes
            else:
                logging.error("Can't find video info.")
                return episodes
        janson = json.loads(match.group(1))
        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]

        if "show" in page["item"] and "seasons" in page["item"]["show"]:
            for i in page["item"]["show"]["seasons"]["items"]:
                seasons.append(f'https://www.dr.dk/drtv{i["path"]}')

        if seasons:
            for season in seasons:
                data = self.http.get(season).text
                match = re.search("__data = ([^<]+)</script>", data)
                janson = json.loads(match.group(1))
                page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
                episodes.extend(self._get_episodes(page))
        else:
            episodes.extend(self._get_episodes(page))

        if config.get("all_last") != -1:
            episodes = episodes[: config.get("all_last")]
        else:
            episodes.reverse()

        return episodes

    def _get_episodes(self, page):
        episodes = []
        if "episodes" in page["item"]:
            entries = page["item"]["episodes"]["items"]
            for i in entries:
                episodes.append(f'https://www.dr.dk/drtv{i["watchPath"]}')

        return episodes
