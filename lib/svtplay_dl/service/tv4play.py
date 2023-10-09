# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.utils.http import download_thumbnails


class Tv4play(Service, OpenGraphThumbMixin):
    supported_domains = ["tv4play.se"]

    def get(self):
        token = self._login()
        if token is None:
            yield ServiceError("You need username / password.")
            return

        match = self._getjson(self.get_urldata())
        if not match:
            yield ServiceError("Can't find json data")
            return
        jansson = json.loads(match.group(1))

        if "params" not in jansson["query"]:
            yield ServiceError("Cant find video id for the video")
            return

        key_check = None
        for key in jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"].keys():
            if key.startswith("media"):
                key_check = key
        what = jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"][key_check]["__ref"]

        if what.startswith("Series:"):
            yield ServiceError("Use the video page not the series page")
            return
        else:
            vid = jansson["props"]["apolloStateFromServer"][what]["id"]

        url = f"https://playback2.a2d.tv/play/{vid}?service=tv4play&device=browser&protocol=hls%2Cdash&drm=widevine&browser=GoogleChrome&capabilities=live-drm-adstitch-2%2Cyospace3"
        res = self.http.request("get", url, headers={"Authorization": f"Bearer {token}"})
        if res.status_code > 400:
            yield ServiceError("Can't play this because the video is geoblocked.")
            return
        jansson = res.json()

        item = jansson["metadata"]
        if item["isDrmProtected"]:
            yield ServiceError("We can't download DRM protected content from this site.")
            return

        if item["isLive"]:
            self.config.set("live", True)
        if item["seasonNumber"] > 0:
            self.output["season"] = item["seasonNumber"]
        if item["episodeNumber"] and item["episodeNumber"] > 0:
            self.output["episode"] = item["episodeNumber"]
        self.output["title"] = item["seriesTitle"]
        self.output["episodename"] = item["title"]
        self.output["id"] = str(vid)
        self.output["episodethumbnailurl"] = item["image"]

        if vid is None:
            yield ServiceError("Cant find video id for the video")
            return

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

    def _getjson(self, data):
        match = re.search(r"application\/json\">(.*\})<\/script>", data)
        return match

    def _login(self):
        if self.config.get("username") is None or self.config.get("password") is None:
            return None

        res = self.http.request("get", "https://auth.a2d.tv/_bm/get_params?type=web-jsto")
        if res.status_code > 400:
            return None
        e = res.json()["e"]
        res = self.http.request(
            "post",
            "https://avod-auth-alb.a2d.tv/oauth/authorize",
            json={
                "client_id": "tv4-web",
                "response_type": "token",
                "credentials": {"username": self.config.get("username"), "password": self.config.get("password")},
            },
            headers={"akamai-bm-telemetry": f"a=&&&e={e}"},
        )
        if res.status_code > 400:
            return None
        return res.json()["access_token"]

    def find_all_episodes(self, config):
        episodes = []
        items = []

        parse = urlparse(self.url)
        if parse.path.startswith("/klipp") or parse.path.startswith("/video"):
            logging.warning("Use program page instead of the clip / video page.")
            return episodes

        token = self._login()
        if token is None:
            logging.error("You need username / password.")
            return episodes

        showid, jansson, kind = self._get_seriesid(self.get_urldata(), dict())
        if showid is None:
            logging.error("Cant find any videos")
            return episodes
        if showid is False:
            logging.error("Can't play this because the video is geoblocked.")
            return episodes
        if kind == "Movie":
            return [f"https://www.tv4play.se/video/{showid}"]
        jansson = self._graphdetails(token, showid)
        for season in jansson["data"]["media"]["allSeasonLinks"]:
            graph_list = self._graphql(season["seasonId"])
            for i in graph_list:
                if i not in items:
                    items.append(i)

        items = sorted(items)
        for item in items:
            episodes.append(f"https://www.tv4play.se/video/{item}")

        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        if not episodes:
            logging.warning("Can't find any videos")
        return episodes

    def _get_seriesid(self, data, jansson):
        match = self._getjson(data)
        if not match:
            return None, jansson, None
        jansson = json.loads(match.group(1))
        if "params" not in jansson["query"]:
            return None, jansson, None
        showid = jansson["query"]["params"][0]
        key_check = None
        for key in jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"].keys():
            if key.startswith("media"):
                key_check = key
        what = jansson["props"]["apolloStateFromServer"]["ROOT_QUERY"][key_check]["__ref"]

        if what.startswith("Episode"):
            if "series" not in jansson["props"]["apolloStateFromServer"][what]:
                return False, jansson, what[: what.index(":")]
            series = jansson["props"]["apolloStateFromServer"][what]["series"]["__ref"].replace("Series:", "")
            res = self.http.request("get", f"https://www.tv4play.se/program/{series}/")
            showid, jansson = self._get_seriesid(res.text, jansson)
        return showid, jansson, what[: what.index(":")]

    def _graphdetails(self, token, show):
        data = {
            "operationName": "ContentDetailsPage",
            "query": "query ContentDetailsPage($programId: ID!, $recommendationsInput: MediaRecommendationsInput!, $seriesSeasonInput: SeriesSeasonInput!) {\n  media(id: $programId) {\n    __typename\n    ... on Movie {\n      __typename\n      id\n      title\n      genres\n      slug\n      productionYear\n      progress {\n        __typename\n        percent\n        position\n      }\n      productionCountries {\n        __typename\n        countryCode\n        name\n      }\n      playableFrom {\n        __typename\n        isoString\n        humanDateTime\n      }\n      playableUntil {\n        __typename\n        isoString\n        humanDateTime\n        readableDistance(type: DAYS_LEFT)\n      }\n      video {\n        __typename\n        ...VideoFields\n      }\n      parentalRating {\n        __typename\n        ...ParentalRatingFields\n      }\n      credits {\n        __typename\n        ...MovieCreditsFields\n      }\n      label {\n        __typename\n        ...LabelFields\n      }\n      images {\n        __typename\n        main16x7 {\n          __typename\n          ...ImageFieldsLight\n        }\n        main16x9 {\n          __typename\n          ...ImageFieldsFull\n        }\n        poster2x3 {\n          __typename\n          ...ImageFieldsLight\n        }\n        logo {\n          __typename\n          ...ImageFieldsLight\n        }\n      }\n      synopsis {\n        __typename\n        brief\n        long\n        medium\n        short\n      }\n      trailers {\n        __typename\n        mp4\n        webm\n      }\n      recommendations(input: $recommendationsInput) {\n        __typename\n        pageInfo {\n          __typename\n          ...PageInfoFields\n        }\n        items {\n          __typename\n          ...RecommendedSeriesMediaItem\n          ...RecommendedMovieMediaItem\n        }\n      }\n      hasPanels\n      isPollFeatureEnabled\n      humanCallToAction\n      upsell {\n        __typename\n        tierId\n      }\n    }\n    ... on Series {\n      __typename\n      id\n      title\n      numberOfAvailableSeasons\n      genres\n      category\n      slug\n      hasPanels\n      isPollFeatureEnabled\n      upsell {\n        __typename\n        tierId\n      }\n      cdpPageOverride {\n        __typename\n        id\n      }\n      upcomingEpisode {\n        __typename\n        ...UpcomingEpisodeFields\n      }\n      trailers {\n        __typename\n        mp4\n        webm\n      }\n      parentalRating {\n        __typename\n        ...ParentalRatingFields\n      }\n      credits {\n        __typename\n        ...SeriesCreditsFields\n      }\n      label {\n        __typename\n        ...LabelFields\n      }\n      images {\n        __typename\n        main16x7 {\n          __typename\n          ...ImageFieldsLight\n        }\n        main16x9 {\n          __typename\n          ...ImageFieldsFull\n        }\n        poster2x3 {\n          __typename\n          ...ImageFieldsLight\n        }\n        logo {\n          __typename\n          ...ImageFieldsLight\n        }\n      }\n      synopsis {\n        __typename\n        brief\n        long\n      }\n      allSeasonLinks {\n        __typename\n        seasonId\n        title\n        numberOfEpisodes\n      }\n      seasonLinks(seriesSeasonInput: $seriesSeasonInput) {\n        __typename\n        items {\n          __typename\n          seasonId\n          numberOfEpisodes\n        }\n      }\n      suggestedEpisode {\n        __typename\n        humanCallToAction\n        episode {\n          __typename\n          id\n          playableFrom {\n            __typename\n            isoString\n          }\n          playableUntil {\n            __typename\n            isoString\n          }\n          progress {\n            __typename\n            percent\n            position\n          }\n          video {\n            __typename\n            ...VideoFields\n          }\n        }\n      }\n      recommendations(input: $recommendationsInput) {\n        __typename\n        pageInfo {\n          __typename\n          ...PageInfoFields\n        }\n        items {\n          __typename\n          ...RecommendedSeriesMediaItem\n          ...RecommendedMovieMediaItem\n        }\n      }\n    }\n    ... on SportEvent {\n      __typename\n      id\n      league\n      arena\n      country\n      round\n      inStudio\n      commentators\n      access {\n        __typename\n        hasAccess\n      }\n      title\n      productionYear\n      images {\n        __typename\n        main16x7 {\n          __typename\n          ...ImageFieldsFull\n        }\n        main16x9 {\n          __typename\n          ...ImageFieldsFull\n        }\n        poster2x3 {\n          __typename\n          ...ImageFieldsLight\n        }\n      }\n      trailers {\n        __typename\n        mp4\n      }\n      synopsis {\n        __typename\n        brief\n        short\n        long\n        medium\n      }\n      playableFrom {\n        __typename\n        isoString\n        humanDateTime\n      }\n      playableUntil {\n        __typename\n        isoString\n        humanDateTime\n        readableDistance(type: DAYS_LEFT)\n      }\n      liveEventEnd {\n        __typename\n        isoString\n      }\n      isLiveContent\n    }\n  }\n}\nfragment VideoFields on Video {\n  __typename\n  duration {\n    __typename\n    readableShort\n    seconds\n  }\n  id\n  isDrmProtected\n  isLiveContent\n  vimondId\n  access {\n    __typename\n    hasAccess\n  }\n}\nfragment ParentalRatingFields on ParentalRating {\n  __typename\n  finland {\n    __typename\n    ageRestriction\n    reason\n  }\n  sweden {\n    __typename\n    ageRecommendation\n    suitableForChildren\n  }\n}\nfragment MovieCreditsFields on MovieCredits {\n  __typename\n  actors {\n    __typename\n    characterName\n    name\n    type\n  }\n  directors {\n    __typename\n    name\n    type\n  }\n}\nfragment LabelFields on Label {\n  __typename\n  airtime\n  announcement\n  contentDetailsPage\n  recurringBroadcast\n}\nfragment ImageFieldsLight on Image {\n  __typename\n  source\n}\nfragment ImageFieldsFull on Image {\n  __typename\n  source\n  meta {\n    __typename\n    muteBgColor {\n      __typename\n      hex\n    }\n  }\n}\nfragment PageInfoFields on PageInfo {\n  __typename\n  hasNextPage\n  nextPageOffset\n  totalCount\n}\nfragment RecommendedSeriesMediaItem on RecommendedSeries {\n  __typename\n  series {\n    __typename\n    id\n    title\n    images {\n      __typename\n      cover2x3 {\n        __typename\n        source\n      }\n      main16x9 {\n        __typename\n        source\n        meta {\n          __typename\n          muteBgColor {\n            __typename\n            hex\n          }\n        }\n      }\n    }\n    label {\n      __typename\n      ...LabelFields\n    }\n    isPollFeatureEnabled\n  }\n}\nfragment RecommendedMovieMediaItem on RecommendedMovie {\n  __typename\n  movie {\n    __typename\n    id\n    title\n    images {\n      __typename\n      cover2x3 {\n        __typename\n        source\n      }\n      main16x9 {\n        __typename\n        source\n        meta {\n          __typename\n          muteBgColor {\n            __typename\n            hex\n          }\n        }\n      }\n    }\n    label {\n      __typename\n      ...LabelFields\n    }\n    isPollFeatureEnabled\n  }\n}\nfragment UpcomingEpisodeFields on UpcomingEpisode {\n  __typename\n  id\n  title\n  playableFrom {\n    __typename\n    humanDateTime\n    isoString\n  }\n  image {\n    __typename\n    main16x9 {\n      __typename\n      ...ImageFieldsLight\n    }\n  }\n}\nfragment SeriesCreditsFields on SeriesCredits {\n  __typename\n  directors {\n    __typename\n    name\n    type\n  }\n  hosts {\n    __typename\n    name\n    type\n  }\n  actors {\n    __typename\n    characterName\n    name\n    type\n  }\n}",
            "variables": {
                "programId": show,
                "recommendationsInput": {"limit": 10, "offset": 0, "types": ["MOVIE", "SERIES"]},
                "seriesSeasonInput": {"limit": 10, "offset": 0},
            },
        }
        res = self.http.request(
            "post",
            "https://client-gateway.tv4.a2d.tv/graphql",
            headers={"Client-Name": "tv4-web", "Client-Version": "4.0.0", "Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            json=data,
        )
        return res.json()

    def _graphql(self, show):
        items = []
        nr = 0
        total = 100
        while nr <= total:
            data = {
                "operationName": "SeasonEpisodes",
                "query": "query SeasonEpisodes($seasonId: ID!, $input: SeasonEpisodesInput!) {\n  season(id: $seasonId) {\n    __typename\n    numberOfEpisodes\n    episodes(input: $input) {\n      __typename\n      initialSortOrder\n      pageInfo {\n        __typename\n        ...PageInfoFields\n      }\n      items {\n        __typename\n        ...EpisodeFields\n      }\n    }\n  }\n}\nfragment PageInfoFields on PageInfo {\n  __typename\n  hasNextPage\n  nextPageOffset\n  totalCount\n}\nfragment EpisodeFields on Episode {\n  __typename\n  id\n  title\n  playableFrom {\n    __typename\n    readableDistance\n    timestamp\n    isoString\n    humanDateTime\n  }\n  playableUntil {\n    __typename\n    readableDistance(type: DAYS_LEFT)\n    timestamp\n    isoString\n    humanDateTime\n  }\n  liveEventEnd {\n    __typename\n    isoString\n    humanDateTime\n    timestamp\n  }\n  progress {\n    __typename\n    percent\n    position\n  }\n  episodeNumber\n  synopsis {\n    __typename\n    short\n    brief\n    medium\n  }\n  seasonId\n  series {\n    __typename\n    id\n    title\n    images {\n      __typename\n      main16x9Annotated {\n        __typename\n        source\n      }\n    }\n  }\n  images {\n    __typename\n    main16x9 {\n      __typename\n      ...ImageFieldsFull\n    }\n  }\n  video {\n    __typename\n    ...VideoFields\n  }\n  isPollFeatureEnabled\n  parentalRating {\n    __typename\n    finland {\n      __typename\n      ageRestriction\n      reason\n      containsProductPlacement\n    }\n  }\n}\nfragment ImageFieldsFull on Image {\n  __typename\n  source\n  meta {\n    __typename\n    muteBgColor {\n      __typename\n      hex\n    }\n  }\n}\nfragment VideoFields on Video {\n  __typename\n  duration {\n    __typename\n    readableShort\n    seconds\n  }\n  id\n  isDrmProtected\n  isLiveContent\n  vimondId\n  access {\n    __typename\n    hasAccess\n  }\n}",
                "variables": {"input": {"limit": 16, "offset": nr, "sortOrder": "ASC"}, "seasonId": show},
            }

            res = self.http.request(
                "post",
                "https://client-gateway.tv4.a2d.tv/graphql",
                headers={"Client-Name": "tv4-web", "Client-Version": "4.0.0", "Content-Type": "application/json"},
                json=data,
            )
            janson = res.json()
            total = janson["data"]["season"]["episodes"]["pageInfo"]["totalCount"]
            for mediatype in janson["data"]["season"]["episodes"]["items"]:
                items.append(mediatype["id"])
            nr += 12
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
