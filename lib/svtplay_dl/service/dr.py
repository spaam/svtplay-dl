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
        apimatch = re.search("CLIENT_SERVICE_URL='([^']+)", data)
        if not apimatch:
            yield ServiceError("Can't find api server.")
            return
        apiserver = apimatch.group(1)
        janson = json.loads(match.group(1))
        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
        resolution = None
        vid = None

        if page["key"] != "Watch":
            yield ServiceError("Wrong url, need to be video url")
            return
        if "item" in page["entries"][0]:
            offers = page["entries"][0]["item"]["offers"]
        elif "item" in page:
            offers = page["item"]["offers"]

        self.output["id"] = page["entries"][0]["item"]["id"]
        if "season" in page["entries"][0]["item"]:
            self.output["title"] = page["entries"][0]["item"]["season"]["title"]
            self.output["season"] = page["entries"][0]["item"]["season"]["seasonNumber"]
            self.output["episode"] = page["entries"][0]["item"]["episodeNumber"]
            self.output["episodename"] = page["entries"][0]["item"]["contextualTitle"]
        elif "title" in page["entries"][0]["item"]:
            self.output["title"] = page["entries"][0]["item"]["title"]

        offerlist = []
        for i in offers:
            if i["deliveryType"] == "StreamOrDownload":
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

        entries = []
        for i in offerlist:
            vid, resolution = i
            url = (
                f"{apiserver}/account/items/{vid}/videos?delivery=stream&device=web_browser&"
                f"ff=idp%2Cldp&lang=da&resolution={resolution}&sub=Anonymous"
            )
            res = self.http.request("get", url, headers={"x-authorization": f"Bearer {token}"})
            if res.status_code > 400:
                yield ServiceError("Can't find the video or its geoblocked")
                return
            for video in res.json():
                if video["accessService"] == "StandardVideo" and video["format"] == "video/hls":
                    res = self.http.request("get", video["url"])
                    if res.status_code > 400:
                        yield ServiceError("Can't play this because the video is geoblocked or not available.")
                    else:
                        hls = hlsparse(self.config, res, video["url"], output=self.output)
                        entries.append(hls)
                        if len(video["subtitles"]) > 0:
                            for i in video["subtitles"]:
                                sub = subtitle_probe(copy.copy(self.config), i["link"], name=i["language"], output=self.output)
                                entries.append(sub)
            subs = []
            for entry in entries:
                for i in entry:
                    if isinstance(i, subtitle):
                        subs.append(i)
                    else:
                        yield i

            if subs:
                if any("Dansk" == y.name for y in subs):
                    for i in subs:
                        if i.name == "Dansk":
                            yield i
                elif any("CombinedLanguageSubtitles" == y.name for y in subs):
                    for i in subs:
                        if i.name == "CombinedLanguageSubtitles":
                            yield i
                else:
                    yield from subs

    def find_all_episodes(self, config):
        episodes = []
        seasons = []
        data = self.get_urldata()
        match = re.search("__data = ([^<]+)</script>", data)
        if not match:
            logging.error("Can't find video info.")
            return episodes

        janson = json.loads(match.group(1))

        if "/saeson/" in self.url:
            page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]
            for i in page["item"]["show"]["seasons"]["items"]:
                seasons.append(f'https://www.dr.dk/drtv{i["path"]}')

        page = janson["cache"]["page"][list(janson["cache"]["page"].keys())[0]]

        if (
            "item" in page["entries"][0]
            and "season" in page["entries"][0]["item"]
            and "show" in page["entries"][0]["item"]["season"]
            and "seasons" in page["entries"][0]["item"]["season"]["show"]
        ):
            for i in page["entries"][0]["item"]["season"]["show"]["seasons"]["items"]:
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
