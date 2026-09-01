import copy
import json
import logging
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.subtitle import subtitle_probe


class Svt(Svtplay):
    supported_domains = ["svt.se", "www.svt.se"]

    def get(self):
        page = _page(_stream_data(self.get_urldata()))
        if page is None:
            yield ServiceError("Can't find video info.")
            return

        video = _main_video(page)
        if not video:
            yield ServiceError("Can't find any videos")
            return

        res = self.http.get(f"https://api.svt.se/video/{video['svtId']}")

        janson = res.json()
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if "url" in i:
                    yield from subtitle_probe(copy.copy(self.config), i["url"], output=self.output)

        yield from self._get_video(janson)

    def find_all_episodes(self, config):
        page = _page(_stream_data(self.get_urldata()))
        if page is None:
            logging.error("Can't find video info.")
            return []

        videos = [f"https://www.svtplay.se/video/{svt_id}" for svt_id in _all_videos(page)]
        if not videos:
            logging.error("Can't find any videos.")
            return videos

        if not self.config.get("reverse_list"):
            videos = videos[::-1]

        if config.get("all_last") > 0:
            return videos[: config.get("all_last")]
        return videos


def _stream_data(data):
    """Decode the turbo-stream payload that svt.se embeds in its pages.

    The payload is a flat array where objects are {"_<keyindex>": <valueindex>}
    and both indexes point back into the array. Negative values are sentinels
    for null and undefined.
    """
    chunks = re.findall(r'streamController\.enqueue\("((?:[^"\\]|\\.)*)"\)', data)
    if not chunks:
        return None

    try:
        flat = json.loads("".join(json.loads(f'"{chunk}"') for chunk in chunks))
    except json.decoder.JSONDecodeError:
        return None
    if not isinstance(flat, list) or not flat:
        return None

    cache = {}

    def unflatten(index):
        if not isinstance(index, int) or index < 0 or index >= len(flat):
            return None
        if index in cache:
            return cache[index]

        value = flat[index]
        # Cache before recursing, the payload is deduplicated and can point back
        # at something we are still building.
        if isinstance(value, dict):
            item = cache[index] = {}
            for key, pos in value.items():
                item[flat[int(key[1:])]] = unflatten(pos)
        elif isinstance(value, list):
            item = cache[index] = []
            for pos in value:
                item.append(unflatten(pos))
        else:
            item = cache[index] = value
        return item

    return unflatten(0)


def _page(janson):
    if not isinstance(janson, dict):
        return None
    for data in janson.get("loaderData", {}).values():
        if isinstance(data, dict) and isinstance(data.get("page"), dict):
            return data["page"]
    return None


def _main_video(page):
    """The video the page url is about, as opposed to anything else it embeds."""
    for key in ["topMedia", "media", "video"]:
        data = page.get(key)
        if isinstance(data, dict) and data.get("svtId"):
            return data
    return None


def _all_videos(page):
    """Every video on the page, the main one first.

    They turn up in a lot of places: topMedia on articles, body on longer ones,
    liveStream posts on live reports and tagFeed on topic pages.
    """
    ids = []
    seen = set()

    def find(data):
        if id(data) in seen:
            return
        seen.add(id(data))

        if isinstance(data, dict):
            svt_id = data.get("svtId")
            if svt_id and svt_id not in ids:
                ids.append(svt_id)
            for value in data.values():
                find(value)
        elif isinstance(data, list):
            for value in data:
                find(value)

    find(_main_video(page))
    find(page)
    return ids
