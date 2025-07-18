import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.subtitle import subtitle_probe


class Svt(Svtplay):
    supported_domains = ["svt.se", "www.svt.se"]

    def get(self):
        vid = None
        data = self.get_urldata()
        match = re.search("urqlState: ({.*})", data)

        janson = json.loads(match.group(1))
        for key in list(janson.keys()):
            janson2 = json.loads(janson[key]["data"])
            if "page" in janson2 and "topMedia" in janson2["page"]:
                vid = janson2["page"]["topMedia"]["svtId"]
        if not vid:
            yield ServiceError("Can't find any videos")
            return
        res = self.http.get(f"https://api.svt.se/video/{vid}")

        janson = res.json()
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if "url" in i:
                    yield from subtitle_probe(copy.copy(self.config), i["url"], output=self.output)

        yield from self._get_video(janson)
