import codecs
import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.subtitle import subtitle


class Svt(Svtplay):
    supported_domains = ["svt.se", "www.svt.se"]

    def get(self):
        data = self.get_urldata()
        match = re.search("n.reduxState=(.*);", data)
        if not match:
            match = re.search(r"stateData = JSON.parse\(\"(.*)\"\)\<\/script", data)
            if not match:
                yield ServiceError("Cant find video info.")
                return
            janson = json.loads(codecs.escape_decode(match.group(1))[0].decode("utf-8"))
            if janson["recipe"]["content"]["data"]["videoClips"]:
                vid = janson["recipe"]["content"]["data"]["videoClips"][0]["id"]
            else:
                vid = janson["recipe"]["content"]["data"]["videoEpisodes"][0]["id"]
            res = self.http.get(f"https://api.svt.se/videoplayer-api/video/{vid}")
        else:
            janson = json.loads(match.group(1))
            vid = janson["areaData"]["articles"][list(janson["areaData"]["articles"].keys())[0]]["media"][0]["image"]["svtId"]
            res = self.http.get(f"https://api.svt.se/video/{vid}")

        janson = res.json()
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if i["format"] == "websrt" and "url" in i:
                    yield subtitle(copy.copy(self.config), "wrst", i["url"], output=self.output)

        videos = self._get_video(janson)
        yield from videos
