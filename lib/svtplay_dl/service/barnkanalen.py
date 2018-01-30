# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json


from svtplay_dl.log import log
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.utils.urllib import urlparse, urljoin, parse_qs
from svtplay_dl.error import ServiceError


class Barnkanalen(Svtplay):
    supported_domains = ['svt.se']
    supported_path = "/barnkanalen"

    @classmethod
    def handles(cls, url):
        urlp = urlparse(url)

        correctpath = urlp.path.startswith(cls.supported_path)
        if urlp.netloc in cls.supported_domains and correctpath:
            return True

        # For every listed domain, try with www. subdomain as well.
        if urlp.netloc in ['www.' + x for x in cls.supported_domains] and correctpath:
            return True

        return False

    def get(self):
        parse = urlparse(self.url)

        query = parse_qs(parse.query)
        self.access = None
        if "accessService" in query:
            self.access = query["accessService"]

        match = re.search("__barnplay'] = ({.*});", self.get_urldata())
        if not match:
            yield ServiceError("Can't find video info.")
            return

        janson = json.loads(match.group(1))["context"]["dispatcher"]["stores"]["ApplicationStateStore"]["data"]
        janson["video"] = janson["categoryStateCache"]["karaktarer"]["episodeModel"]

        if "title" not in janson["video"]:
            yield ServiceError("Can't find any video on that page.")
            return

        if "live" in janson["video"]:
            self.options.live = janson["video"]["live"]

        if self.options.output_auto:
            self.options.service = "svtplay"
            self.options.output = self.outputfilename(janson["video"], self.options.output)

        if self.exclude():
            yield ServiceError("Excluding video.")
            return

        if "programVersionId" in janson["video"]:
            vid = janson["video"]["programVersionId"]
        else:
            vid = janson["video"]["id"]
        res = self.http.get("http://api.svt.se/videoplayer-api/video/{0}".format(vid))
        try:
            janson = res.json()
        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {0}".format(res.request.url))
            return
        videos = self._get_video(janson)
        for i in videos:
            yield i

    def find_all_episodes(self, options):
        videos = []
        match = re.search("__barnplay'] = ({.*});", self.get_urldata())
        if not match:
            log.error("Couldn't retrieve episode list.")
            return
        else:
            dataj = json.loads(match.group(1))
            dataj = dataj["context"]["dispatcher"]["stores"]["EpisodesStore"]
            showId = list(dataj["data"].keys())[0]
            items = dataj["data"][showId]["episodes"]
            for i in items:
                program = i
                videos = self.videos_to_list(program, videos)
            videos.reverse()

        episodes = [urljoin("http://www.svt.se", x) for x in videos]

        if options.all_last > 0:
            return episodes[-options.all_last:]
        return episodes

    def videos_to_list(self, lvideos, videos):
        url = self.url + "/" + str(lvideos["id"])
        parse = urlparse(url)
        if parse.path not in videos:
            filename = self.outputfilename(lvideos, self.options.output)
            if not self.exclude2(filename):
                videos.append(parse.path)

        return videos
