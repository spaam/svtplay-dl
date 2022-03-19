import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Angelstudios(Service):
    supported_domains = ["watch.angelstudios.com"]

    def get(self):
        data = self.get_urldata()
        match = re.search(r'contentUrl": "([^"]+)"', data)
        if not match:
            yield ServiceError("Can't find the video")
            return
        hls_playlist = match.group(1)
        match = re.search(r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>", data)
        janson = json.loads(match.group(1))
        if "episode" in janson["props"]["pageProps"]["data"]:
            self.output["season"] = janson["props"]["pageProps"]["data"]["episode"]["seasonNumber"]
            self.output["episode"] = janson["props"]["pageProps"]["data"]["episode"]["episodeNumber"]
            self.output["episodename"] = janson["props"]["pageProps"]["data"]["episode"]["subtitle"]
            self.output["title"] = janson["props"]["pageProps"]["data"]["episode"]["projectSlug"]
        else:
            self.output["title"] = janson["props"]["pageProps"]["data"]["video"]["projectSlug"]
            self.output["episodename"] = f'{janson["props"]["pageProps"]["data"]["video"]["slug"].lower()}'
        yield from hlsparse(self.config, self.http.request("get", hls_playlist), hls_playlist, self.output)

    def find_all_episodes(self, config):
        episodes = []

        graphql = (
            "fragment CoreEpisodeFields on Episode {\n  id\n  guid\n  episodeNumber\n  seasonNumber\n"
            "seasonId\n  subtitle\n  description\n  name\n  posterCloudinaryPath\n  projectSlug\n"
            "  releaseDate\n  source {\n    captions\n    credits\n    duration\n    url\n    __typename\n"
            "  }\n  upNext {\n    id\n    guid\n    __typename\n  }\n  __typename\n}\n\nquery videoList {\n"
            '  project(slug: "the-chosen") {\n    seasons {\n      id\n      name\n      episodes {\n'
            "        ...CoreEpisodeFields\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}"
        )
        res = self.http.post("https://chosen-hydra.vidangel.com/graphql", json={"operationName": "videoList", "variables": {}, "query": graphql})
        for season in res.json()["data"]["project"]["seasons"]:
            for episode in season["episodes"]:
                episodes.append(
                    f'https://watch.angelstudios.com/thechosen/watch/episodes/season-{episode["seasonNumber"]}-episode-{episode["episodeNumber"]}-{slugify(episode["subtitle"])}?ap=true',
                )

        if self.config.get("include_clips"):
            graphql = (
                "fragment CoreVideoFields on Video {\n  id\n  guid\n  slug\n  title\n  subtitle\n  page\n"
                "  projectSlug\n  posterCloudinaryPath\n  source {\n    url\n    credits\n    duration\n"
                "    name\n    __typename\n  }\n  __typename\n}\n\nquery getVideos($page: String) {\n"
                "  videos(page: $page) {\n    ...CoreVideoFields\n    __typename\n  }\n}"
            )
            res = self.http.post(
                "https://chosen-hydra.vidangel.com/graphql",
                json={"operationName": "getVideos", "variables": {"page": "bonus"}, "query": graphql},
            )
            for video in res.json()["data"]["videos"]:
                episodes.append(f'https://watch.angelstudios.com/thechosen/watch/bonus/{video["guid"]}?ap=true')

            graphql = (
                "fragment CoreVideoFields on Video {\n  id\n  guid\n  slug\n  title\n  subtitle\n  page\n"
                "  projectSlug\n  posterCloudinaryPath\n  source {\n    url\n    credits\n    duration\n"
                "    name\n    __typename\n  }\n  __typename\n}\n\nquery getVideos($page: String) {\n"
                "  videos(page: $page) {\n    ...CoreVideoFields\n    __typename\n  }\n}"
            )
            res = self.http.post(
                "https://chosen-hydra.vidangel.com/graphql",
                json={"operationName": "getVideos", "variables": {"page": "deepDive"}, "query": graphql},
            )
            for video in res.json()["data"]["videos"]:
                episodes.append(f'https://watch.angelstudios.com/thechosen/watch/deepDive/{video["guid"]}?ap=true')

        return episodes


def slugify(text: str):
    return re.sub(r"[\W_]+", "-", text.lower())
