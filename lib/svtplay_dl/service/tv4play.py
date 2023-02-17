# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
from datetime import datetime
from datetime import timedelta
from urllib.parse import urlparse

import requests
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.utils.http import download_thumbnails


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4play.se"]

    def get(self):
        parse = urlparse(self.url)
        if parse.path[:8] == "/kanaler":
            end_time_stamp = (datetime.utcnow() - timedelta(minutes=1, seconds=20)).replace(microsecond=0)
            start_time_stamp = end_time_stamp - timedelta(minutes=1)

            url = (
                f"https://bbr-l2v.akamaized.net/live/{parse.path[9:]}/master.m3u8?in={start_time_stamp.isoformat()}&out={end_time_stamp.isoformat()}?"
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
        if "assetId" not in jansson["query"]:
            yield ServiceError("Cant find video id for the video")
            return

        vid = jansson["query"]["assetId"]
        janson2 = jansson["props"]["initialApolloState"]
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
        self.output["episodethumbnailurl"] = item["image"]

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

        url = f"https://playback2.a2d.tv/play/{vid}?service=tv4&device=browser&browser=GoogleChrome&protocol=hls%2Cdash&drm=widevine&capabilities=live-drm-adstitch-2%2Cexpired_assets"
        try:
            res = self.http.request("get", url, cookies=self.cookies)
        except requests.exceptions.RetryError:
            res = requests.get(url, cookies=self.cookies)
            yield ServiceError(f"Can't play this because the video is geoblocked: {res.json()['message']}")
            return
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked or not available.")
            return

        jansson = res.json()
        if jansson["playbackItem"]["type"] == "hls":
            yield from hlsparse(
                self.config,
                self.http.request("get", jansson["playbackItem"]["manifestUrl"]),
                jansson["playbackItem"]["manifestUrl"],
                output=self.output,
                httpobject=self.http,
            )
            yield from dashparse(
                self.config,
                self.http.request("get", jansson["playbackItem"]["manifestUrl"].replace(".m3u8", ".mpd")),
                jansson["playbackItem"]["manifestUrl"].replace(".m3u8", ".mpd"),
                output=self.output,
                httpobject=self.http,
            )

    def _getjson(self):
        match = re.search(r"application\/json\">(.*\})<\/script>", self.get_urldata())
        return match

    def find_all_episodes(self, config):
        episodes = []
        items = []
        show = None
        match = self._getjson()
        jansson = json.loads(match.group(1))
        if "nid" not in jansson["query"]:
            logging.info("Can't find show name.")
            return episodes
        show = jansson["query"]["nid"]
        graph_list = self._graphql(show, "EPISODE")
        for i in graph_list:
            if i not in items:
                items.append(i)
        if config.get("include_clips"):
            items.extend(self._graphql(show, "CLIP"))

        items = sorted(items)
        for item in items:
            episodes.append(f"https://www.tv4play.se/program/{show}/{item}")

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes

    def _graphql(self, show, panel_type):
        items = []
        gql = {
            "variables": {
                "programPanelsInput": {"offset": 0, "limit": 1000},
                "videoAssetListInput": {"limit": 100, "offset": 0, "sortOrder": "ASCENDING"},
                "programNid": show,
            },
            "query": "query Seasons($programNid: String, $videoAssetListInput: VideoAssetListInput!, $programPanelsInput: ProgramPanelsInput!)"
            " {\n  program(nid: $programNid) {\n    __typename\n    upcoming {\n      __typename\n      ...EpisodeVideoAssetField\n    }\n"
            "    panels2(input: $programPanelsInput) {\n      __typename\n      pageInfo {\n        __typename\n        totalCount\n"
            "        hasNextPage\n        nextPageOffset\n      }\n      items {\n        __typename\n        ...EpisodePanelField\n      }\n"
            "    }\n  }\n}fragment EpisodeVideoAssetField on VideoAsset {\n  __typename\n  id\n  title\n  description\n  expireDateTime\n"
            "  humanDuration\n  freemium\n  broadcastDateTime\n  live\n  daysLeftInService\n  duration\n  season\n  episode\n"
            "  humanBroadcastDateTime\n  humanBroadcastDateWithWeekday\n  program {\n    __typename\n    nid\n    name\n    displayCategory\n"
            "    images2 {\n      __typename\n      main16x9 {\n        __typename\n        url\n      }\n    }\n  }\n  progress {\n"
            "    __typename\n    position\n    percentage\n  }\n  image2 {\n    __typename\n    url\n  }\n}fragment"
            " EpisodePanelField on VideoPanel {\n  __typename\n  id\n  name\n  assetType\n  totalNumberOfEpisodes\n"
            "  videoList2(input: $videoAssetListInput) {\n    __typename\n    pageInfo {\n      __typename\n      totalCount\n"
            "      hasNextPage\n      nextPageOffset\n    }\n    initialSortOrder\n    items {\n      __typename\n      id\n"
            "      title\n      ...EpisodeVideoAssetField\n    }\n  }\n}",
        }
        res = self.http.request("post", "https://graphql.tv4play.se/graphql", json=gql)
        janson = res.json()

        for mediatype in janson["data"]["program"]["panels2"]["items"]:
            offset = 0
            if mediatype["assetType"] != panel_type:
                continue
            moreData = mediatype["videoList2"]["pageInfo"]["hasNextPage"]
            seasonid = mediatype["id"]
            for video in mediatype["videoList2"]["items"]:
                items.append(video["id"])

            while moreData:
                offset += 100
                gql2 = {
                    "variables": {"id": seasonid, "videoAssetListInput": {"limit": 100, "sortOrder": "ASCENDING", "offset": offset}},
                    "query": "query MoreEpisodes($id: String!, $videoAssetListInput: VideoAssetListInput!) {\n"
                    "  videoPanel(id: $id) {\n    __typename\n    videoList2(input: $videoAssetListInput) {\n      __typename\n"
                    "      pageInfo {\n        __typename\n        totalCount\n        hasNextPage\n        nextPageOffset\n"
                    "      }\n      items {\n        __typename\n        id\n        title\n        ...EpisodeVideoAssetField\n"
                    "      }\n    }\n  }\n}fragment EpisodeVideoAssetField on VideoAsset {\n  __typename\n  id\n  title\n"
                    "  description\n  expireDateTime\n  humanDuration\n  freemium\n  broadcastDateTime\n  live\n  daysLeftInService\n"
                    "  duration\n  season\n  episode\n  humanBroadcastDateTime\n  humanBroadcastDateWithWeekday\n  program {\n"
                    "    __typename\n    nid\n    name\n    displayCategory\n    images2 {\n      __typename\n      main16x9 {\n"
                    "        __typename\n        url\n      }\n    }\n  }\n  progress {\n    __typename\n    position\n    percentage\n"
                    "  }\n  image2 {\n    __typename\n    url\n  }\n}",
                }
                res = self.http.request("post", "https://graphql.tv4play.se/graphql", json=gql2)
                moreData = res.json()["data"]["videoPanel"]["videoList2"]["pageInfo"]["hasNextPage"]
                for video in res.json()["data"]["videoPanel"]["videoList2"]["items"]:
                    items.append(video["id"])

        return items

    def get_thumbnail(self, options):
        download_thumbnails(self.output, options, [(False, self.output["episodethumbnailurl"])])


class Tv4(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4.se"]

    def get(self):
        match = re.search(r"application\/json\"\>(\{.*\})\<\/script", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video data'")
            return
        janson = json.loads(match.group(1))
        self.output["id"] = janson["query"]["id"]
        self.output["title"] = janson["query"]["slug"]
        if janson["query"]["type"] == "Article":
            vidasset = janson["props"]["pageProps"]["apolloState"][f"Article:{janson['query']['id']}"]["featured"]["__ref"]
            self.output["id"] = janson["props"]["pageProps"]["apolloState"][vidasset]["id"]
        url = f"https://playback2.a2d.tv/play/{self.output['id']}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine&capabilities=live-drm-adstitch-2%2Cexpired_assets"
        res = self.http.request("get", url, cookies=self.cookies)
        if res.status_code > 200:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        if res.json()["playbackItem"]["type"] == "hls":
            yield from hlsparse(
                self.config,
                self.http.request("get", res.json()["playbackItem"]["manifestUrl"]),
                res.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
