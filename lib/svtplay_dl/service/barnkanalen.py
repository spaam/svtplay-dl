# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import json
import logging
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay


class Barnkanalen(Svtplay):
    supported_domains = ["svt.se"]
    supported_path = "/barnkanalen"
    info_search_expr = r"<script id=\"__NEXT_DATA__\" type=\"application\/json\">({.+})<\/script>"

    @classmethod
    def handles(cls, url):
        urlp = urlparse(url)

        correctpath = urlp.path.startswith(cls.supported_path)
        if urlp.netloc in cls.supported_domains and correctpath:
            return True

        # For every listed domain, try with www. subdomain as well.
        if urlp.netloc in ["www." + x for x in cls.supported_domains] and correctpath:
            return True

        return False

    def get(self):
        data = self.get_urldata()
        match = re.search(self.info_search_expr, data)
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))
        if "episodeId" not in janson["query"]:
            yield ServiceError("need a url with one to be able to download")
            return

        vid = janson["query"]["episodeId"]
        title = janson["props"]["pageProps"]["initialState"]["gridContent"]["featuredContent"]["name"]
        seasonnr = None
        episodenr = None
        episodename = None
        for season in janson["props"]["pageProps"]["initialState"]["gridContent"]["featuredContent"]["associatedContent"]:
            tmp_season = season["name"]
            for episode in season["items"]:
                if "variants" in episode["item"]:
                    svtID = episode["item"]["variants"][0]
                else:
                    svtID = episode["item"]
                if vid == svtID["svtId"]:
                    match = re.search(r"S.song (\d+)", tmp_season)
                    if match:
                        seasonnr = match.group(1)
                    match = re.search(r"^(\d+)\. (.*)$", episode["item"]["name"])
                    if match:
                        episodenr = match.group(1)
                        episodename = match.group(2)
                    else:
                        episodename = episode["item"]["name"]
                    break

        self.output["title"] = title
        self.output["id"] = vid.lower()
        self.output["season"] = seasonnr
        self.output["episode"] = episodenr
        self.output["episodename"] = episodename
        res = self.http.get(f"https://api.svt.se/video/{vid}")
        janson = res.json()
        videos = self._get_video(janson)
        yield from videos

    def find_all_episodes(self, config):
        data = self.get_urldata()
        match = re.search(self.info_search_expr, data)
        if not match:
            logging.error("Can't find video info.")
            return

        janson = json.loads(match.group(1))
        title = janson["query"]["titleSlug"]
        episodes = []
        for season in janson["props"]["pageProps"]["initialState"]["gridContent"]["featuredContent"]["associatedContent"]:
            for episode in season["items"]:
                if "variants" in episode["item"]:
                    svtID = episode["item"]["variants"][0]
                else:
                    svtID = episode["item"]
                episodes.append("https://www.svt.se/barnkanalen/barnplay/{}/{}/".format(title, svtID["svtId"]))
        if config.get("all_last") > 0:
            return episodes[-config.get("all_last") :]
        return episodes
