import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.service.svtplay import timestamp
from svtplay_dl.subtitle import subtitle_probe


class Svt(Svtplay):
    supported_domains = ["svt.se", "www.svt.se"]

    def get(self):
        page = _page(_stream_data(self.get_urldata()))
        if page is None:
            yield ServiceError("Can't find video info.")
            return

        video = None
        for key in ["topMedia", "media", "video"]:
            data = page.get(key)
            if isinstance(data, dict) and data.get("svtId"):
                video = data
                break

        if not video:
            yield ServiceError("Can't find any videos")
            return

        self._set_metadata(page, video)

        res = self.http.get(f"https://api.svt.se/video/{video['svtId']}")

        janson = res.json()
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if "url" in i:
                    yield from subtitle_probe(copy.copy(self.config), i["url"], output=self.output)

        yield from self._get_video(janson)

    def _set_metadata(self, page, video):
        section = page.get("section") or {}
        poster = video.get("poster") or {}

        self.output["title"] = section.get("name") or page.get("title")
        self.output["title_nice"] = self.output["title"]
        self.output["episodename"] = video.get("metadataTitle") or video.get("title") or page.get("title")
        self.output["id"] = video["svtId"]
        self.output["episodedescription"] = video.get("description")
        self.output["episodethumbnailurl"] = poster.get("metaImage")
        self.output["tvshow"] = False

        if page.get("published"):
            self.output["publishing_datetime"] = timestamp(page["published"])


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
