# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import re
from datetime import datetime
from datetime import timedelta
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4play.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":
            end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = "https://bbr-l2v.akamaized.net/live/{}/master.m3u8?in={}&out={}?".format(
                parse.path[9:],
                start_time_stamp.isoformat(),
                end_time_stamp.isoformat(),
            )

            self.config.set("live", True)
            streams = hlsparse(self.config, self.http.request("get", url), url, output=self.output, hls_time_stamp=True)
            for n in list(streams.keys()):
                yield streams[n]
            return

        match = self._getjson()
        if not match:
            yield ServiceError("Can't find json data")
            return

        jansson = json.loads(match.group(1))
        if "assetId" not in jansson["props"]["pageProps"]:
            yield ServiceError("Cant find video id for the video")
            return

        vid = jansson["props"]["pageProps"]["assetId"]
        janson2 = jansson["props"]["pageProps"]["initialApolloState"]
        item = janson2[f"VideoAsset:{vid}"]

        if item["is_drm_protected"]:
            yield ServiceError("We can't download DRM protected content from this site.")
            return

        if item["live"]:
            self.config.set("live", True)
        if item["season"] > 0:
            self.output["season"] = item["season"]
        if item["episode"] > 0:
            self.output["episode"] = item["episode"]
        self.output["title"] = item["program_nid"]
        self.output["episodename"] = item["title"]
        self.output["id"] = str(vid)

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

        url = f"https://playback-api.b17g.net/media/{vid}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine&browser=GoogleChrome"
        res = self.http.request("get", url, cookies=self.cookies)
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked or not available.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
                httpobject=self.http,
            )
            for n in list(streams.keys()):
                yield streams[n]

    def _getjson(self):
        match = re.search(r"application\/json\">(.*\})<\/script><script", self.get_urldata())
        return match

    def find_all_episodes(self, config):
        episodes = []
        items = []
        show = None
        match = self._getjson()
        jansson = json.loads(match.group(1))
        janson2 = jansson["props"]["pageProps"]["initialApolloState"]
        show = jansson["query"]["nid"]

        program = janson2[f"Program:{show}"]
        episodes_panel = []
        clips_panel = []
        for panel in program["panels"]:
            if panel["assetType"] == "EPISODE":
                params = json.loads(panel["loadMoreParams"])
                if "tags" in params:
                    for tag in params["tags"].split(","):
                        if re.search(r"\d+", tag):
                            episodes_panel.append(tag)
                for key in panel.keys():
                    if "videoList" in key:
                        for video in panel[key]["videoAssets"]:
                            match = re.search(r"VideoAsset:(\d+)", video["__ref"])
                            if match:
                                if match.group(1) not in items:
                                    items.append(int(match.group(1)))
            if config.get("include_clips") and panel["assetType"] == "CLIP":
                params = json.loads(panel["loadMoreParams"])
                if "tags" in params:
                    for tag in params["tags"].split(","):
                        if re.search(r"\d+", tag):
                            clips_panel.append(tag)

        if episodes_panel:
            graph_list = self._graphql(show, episodes_panel, "EPISODE")
            for i in graph_list:
                if i not in items:
                    items.append(i)
        if clips_panel:
            items.extend(self._graphql(show, clips_panel, "CLIP"))

        items = sorted(items)
        for item in items:
            episodes.append(f"https://www.tv4play.se/program/{show}/{item}")

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes

    def _graphql(self, show, panels, panel_type):
        items = []
        for panel in panels:
            offset = 0
            total = 9999
            moreData = True

            while moreData:
                gql = {
                    "variables": {
                        "offset": offset,
                        "limit": 50,
                        "serializedParams": '{"tags":"'
                        + panel
                        + '","tags_mode":"any","sort_order":"asc","type":"'
                        + panel_type.lower()
                        + '","is_live":false,"node_nids_mode":"any","nodes_mode":"any"}',
                        "query": show,
                    },
                    "query": "query SearchVideoAsset($query: String, $limit: Int, $offset: Int, $serializedParams: String)"
                    " {\n  videoAssetSearch(q: $query, offset: $offset, type: "
                    + panel_type
                    + ", limit: $limit, serializedParams: $serializedParams) {\n    __typename\n    totalHits\n    "
                    "videoAssets {\n      __typename\n      ...VideoAssetField\n    }\n  }\n}fragment VideoAssetField "
                    "on VideoAsset {\n  __typename\n  id\n  title\n  tags\n  description\n  image\n  live\n  clip\n  "
                    "season\n  episode\n  hideAds\n  categories\n  publishedDateTime\n  humanPublishedDateTime\n  "
                    "broadcastDateTime\n  humanBroadcastDateTime\n  humanDaysLeftInService\n  humanBroadcastShortDateTime\n  "
                    "expireDateTime\n  productGroups\n  productGroupNids\n  duration\n  humanDuration\n  drmProtected\n  "
                    "freemium\n  geoRestricted\n  startOver\n  progress {\n    __typename\n    ...ProgressField\n  }\n  "
                    "program {\n    __typename\n    ...ProgramField\n  }\n  nextEpisode {\n    __typename\n    id\n    "
                    "title\n    publishedDateTime\n    humanPublishedDateTime\n    duration\n    image\n  }\n}"
                    "fragment ProgressField on Progress {\n  __typename\n  percentage\n  position\n}"
                    "fragment ProgramField on Program {\n  __typename\n  nid\n  name\n  description\n  geoRestricted\n  "
                    "carouselImage\n  image\n  displayCategory\n  genres\n  logo\n  type\n  webview2 {\n    __typename\n    "
                    "id\n    url\n    name\n  }\n  label {\n    __typename\n    label\n    cdpText\n  }\n  actors\n  "
                    "directors\n  upcoming {\n    __typename\n    id\n    image\n    episode\n    humanBroadcastDateWithWeekday\n    "
                    "title\n  }\n  images {\n    __typename\n    main4x3\n    main16x9\n    main16x7\n    main16x9Annotated\n  }\n  "
                    "favorite\n  keepWatchingIgnored\n  cmoreInfo {\n    __typename\n    text\n    link\n  }\n  trailers "
                    "{\n    __typename\n    mp4\n  }\n  trackingData {\n    __typename\n    burt {\n      __typename\n"
                    "      vmanId\n      category\n      tags\n    }\n  }\n}",
                }
                res = self.http.post("https://graphql.tv4play.se/graphql", json=gql)
                total = res.json()["data"]["videoAssetSearch"]["totalHits"]
                for asset in res.json()["data"]["videoAssetSearch"]["videoAssets"]:
                    items.append(asset["id"])
                offset += len(res.json()["data"]["videoAssetSearch"]["videoAssets"])
                if offset >= total:
                    moreData = False
        return items


class Tv4(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4.se"]

    def get(self):
        match = re.search(r"[\/-](\d+)$", self.url)
        if not match:
            yield ServiceError("Cant find video id")
            return
        self.output["id"] = match.group(1)

        match = re.search("data-program-format='([^']+)'", self.get_urldata())
        if not match:
            yield ServiceError("Cant find program name")
            return
        self.output["title"] = match.group(1)

        match = re.search('img alt="([^"]+)" class="video-image responsive"', self.get_urldata())
        if not match:
            yield ServiceError("Cant find title of the video")
            return
        self.output["episodename"] = match.group(1)

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"])
        res = self.http.request("get", url, cookies=self.cookies)
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
            for n in list(streams.keys()):
                yield streams[n]
