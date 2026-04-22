import copy
import datetime
import logging
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import MetadataThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle_probe

RUV_API = "https://api.ruv.is/api/programs/program/{sid}/all"
RUV_VOD = "https://ruv-vod.akamaized.net"


def _highres_image_url(url):
    if not url:
        return None
    return url.replace("/480x/", "/2048x/")


def _parse_season(title, foreign_title, description):
    t = title or ""
    f = foreign_title or ""
    d = (description or "").lower()
    suffixes = [
        ((" 2", " II"), 2),
        ((" 3", " III"), 3),
        ((" 4", " IV"), 4),
        ((" 5", " V"), 5),
        ((" 6", " VI"), 6),
        ((" 7", " VII"), 7),
        ((" 8", " VIII"), 8),
        ((" 9", " IX"), 9),
        ((" 10", " X"), 10),
    ]
    icelandic = [
        ("önnur þáttaröð", 2),
        ("þriðja þáttaröð", 3),
        ("fjórða þáttaröð", 4),
        ("fimmta þáttaröð", 5),
        ("sjötta þáttaröð", 6),
        ("sjöunda þáttaröð", 7),
        ("áttunda þáttaröð", 8),
        ("níunda þáttaröð", 9),
        ("tíunda þáttaröð", 10),
    ]
    for endings, num in suffixes:
        if any(t.endswith(e) or f.endswith(e) for e in endings):
            return num
    for phrase, num in icelandic:
        if phrase in d:
            return num
    return 1


class Ruv(MetadataThumbMixin, Service):
    supported_domains = ["ruv.is"]

    def get(self):
        path = urlparse(self.url).path
        match = re.search(r"/(\d+)/([^/]+)/?$", path)
        if not match:
            yield ServiceError(f"Can't parse series/episode ID from URL: {self.url}")
            return

        sid = match.group(1)
        pid = match.group(2)

        prog, ep = self._fetch_episode(sid, pid)
        if ep is None:
            yield ServiceError(f"Episode {pid} not found in series {sid}")
            return

        file_url = ep.get("file")
        if not file_url or not file_url.startswith(RUV_VOD):
            yield ServiceError(f"No stream URL found for episode {pid}")
            return

        self._set_metadata(prog, ep, pid)

        sub_url = ep.get("subtitles_url")
        if sub_url:
            yield from subtitle_probe(copy.copy(self.config), sub_url, output=copy.copy(self.output))

        yield from hlsparse(
            self.config,
            self.http.request("get", file_url),
            file_url,
            output=self.output,
        )

    def find_all_episodes(self, options):
        path = urlparse(self.url).path
        match = re.search(r"(.*?/(\d+))(?:/[^/]+)?/?$", path)
        if not match:
            return [self.url]
        base_path = match.group(1)
        sid = match.group(2)
        resp = self.http.request("get", RUV_API.format(sid=sid))
        if resp.status_code != 200:
            logging.warning("ruv: failed to fetch series %s", sid)
            return [self.url]

        prog = resp.json()
        episodes = prog.get("episodes", [])
        return [f"https://www.ruv.is{base_path}/{ep['id']}" for ep in episodes if ep.get("file")]

    def _fetch_episode(self, sid, pid):
        resp = self.http.request("get", RUV_API.format(sid=sid))
        if resp.status_code != 200:
            return None, None
        prog = resp.json()
        if not prog or "episodes" not in prog:
            return None, None
        ep = next(
            (e for e in prog["episodes"] if str(e.get("id")) == pid or e.get("slug") == pid or str(e.get("event", "")) == pid),
            None,
        )
        return prog, ep

    def _set_metadata(self, prog, ep, pid):
        self.output["title"] = prog.get("title") or "RUV"
        self.output["id"] = pid
        self.output["episodename"] = ep.get("title") or None
        self.output["tvshow"] = bool(prog.get("multiple_episodes"))
        self.output["showdescription"] = prog.get("short_description")
        self.output["showthumbnailurl"] = _highres_image_url(prog.get("image"))

        ep_desc = ep.get("description")
        if isinstance(ep_desc, list):
            ep_desc = " ".join(ep_desc)
        self.output["episodedescription"] = ep_desc or None
        self.output["episodethumbnailurl"] = _highres_image_url(ep.get("image"))

        if self.output["tvshow"]:
            self.output["season"] = _parse_season(prog.get("title"), prog.get("foreign_title"), ep_desc)
            ep_num = ep.get("number")
            if ep_num is not None:
                try:
                    self.output["episode"] = int(ep_num)
                except (ValueError, TypeError):
                    pass

        firstrun = ep.get("firstrun")
        if firstrun:
            try:
                dt = datetime.datetime.fromisoformat(firstrun.replace("Z", "+00:00"))
                self.output["publishing_datetime"] = int(dt.timestamp())
            except (ValueError, AttributeError):
                pass
