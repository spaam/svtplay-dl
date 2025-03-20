import json
import logging
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay

URL_VIDEO_API = "https://api.svt.se/video/"


class Svtbarn(Svtplay):
    supported_domains = ["svtbarn.se"]

    def get(self):
        urldata = self.get_urldata()

        match = re.search(self.info_search_expr, urldata)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))
        vid = janson["query"]["episodeId"]

        self.output["title"] = janson["query"]["titleSlug"]
        self.output["id"] = vid.lower()
        self.output["episodename"] = janson["query"]["episodeSlug"]

        res = self.http.get(URL_VIDEO_API + vid)
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError(f"Can't decode api request: {res.request.url}")
            return

        if res.status_code >= 400:
            yield ServiceError("Can't find any videos. Is it removed?")
            return

        videos = self._get_video(janson)
        yield from videos

    def find_all_episodes(self, config):
        episodes = []

        urldata = self.get_urldata()

        match = re.search(self.info_search_expr, urldata)
        if not match:
            logging.error("Can't find video info.")
            return episodes

        janson = json.loads(match.group(1))
        titleid = janson["props"]["pageProps"]["initialState"]["currentTitleId"]

        for assoc in janson["props"]["pageProps"]["initialState"]["titles"][titleid]["associatedContent"]:
            if assoc["selectionType"] != "season":
                continue
            for item in assoc["items"]:
                episodes.append(
                    f'https://www.svtbarn.se/{item["item"]["parent"]["slug"]}/{item["item"]["slug"]}/{item["item"]["variants"][0]["svtId"]}',
                )

        return episodes
