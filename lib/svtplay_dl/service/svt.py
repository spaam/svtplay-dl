import re
import json

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay


class Svt(Svtplay):
    supported_domains = ['svt.se', 'www.svt.se']

    def get(self):
        match = re.search("window.svt.nyh.reduxState=({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Cant find video info.")
            return

        janson = json.loads(match.group(1))
        context = janson["appState"]["location"]["context"]
        areaData = janson["areaData"]["articles"][context]["media"]

        res = self.http.get("http://api.svt.se/videoplayer-api/video/{0}".format(areaData[0]["id"]))
        janson = res.json()
        videos = self._get_video(janson)
        for i in videos:
            yield i