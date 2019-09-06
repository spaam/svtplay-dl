import copy
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.subtitle import subtitle


class Svt(Svtplay):
    supported_domains = ["svt.se", "www.svt.se"]

    def get(self):

        data = self.get_urldata()
        match_data_video_id = re.search('data-video-id="(.+?)"', data)

        if match_data_video_id:
            id = match_data_video_id.group(1)

        else:
            yield ServiceError("Cant find video info.")
            return

        res = self.http.get("http://api.svt.se/videoplayer-api/video/{}".format(id))
        janson = res.json()
        if "subtitleReferences" in janson:
            for i in janson["subtitleReferences"]:
                if i["format"] == "websrt" and "url" in i:
                    yield subtitle(copy.copy(self.config), "wrst", i["url"], output=self.output)

        videos = self._get_video(janson)
        yield from videos
