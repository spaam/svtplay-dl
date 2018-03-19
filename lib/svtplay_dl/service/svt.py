import re
import json

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay


class Svt(Svtplay):
    supported_domains = ['svt.se', 'www.svt.se']

    def get(self):

        data = self.get_urldata()
        match = re.search("window.svt.nyh.reduxState=({.*});", data)
        match_data_video_id = re.search("data-video-id=\"(.+?)\"", data)

        if match_data_video_id:
            id = match_data_video_id.group(1)

        elif match:
            janson = json.loads(match.group(1))
            context = janson["appState"]["location"]["context"]
            areaData = janson["areaData"]["articles"][context]["media"]
            id = areaData[0]["id"]

        else:
            yield ServiceError("Cant find video info.")
            return

        res = self.http.get("http://api.svt.se/videoplayer-api/video/{0}".format(id))
        janson = res.json()
        videos = self._get_video(janson)
        for i in videos:
            yield i