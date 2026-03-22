# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ["sverigesradio.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search(r'data-audio-id="(\d+)"', data)
        match2 = re.search(r'data-publication-id="(\w+)"', data)
        if match and match2:
            aid = match.group(1)
            pubid = match2.group(1)
            yield from self.ajax(aid, pubid)
            return

        match = re.search(r'content="sesrplay://play/(\w+)/(\d+)"', data)
        if match:
            yield from self.webapi(match.group(2), match.group(1))
            return

        yield ServiceError("Can't find audio info")
        return

    def ajax(self, aid, pubid):
        for what in ["episode", "secondary", "publication"]:
            language = ""
            apiurl = f"https://sverigesradio.se/playerajax/audio?id={aid}&type={what}&publicationid={pubid}&quality=high"
            resp = self.http.request("get", apiurl)
            if resp.status_code > 400:
                continue
            playerinfo = resp.json()
            if what == "secondary":
                language = "musik"
            yield HTTP(copy.copy(self.config), playerinfo["audioUrl"], 128, output=self.output, language=language)

    def webapi(self, aid, what):
        res = self.http.get(f"https://web-api.sr.se/v1/player/ondemand?id={aid}&type={what}")
        if not res.ok:
            yield ServiceError("Can't find audio info")
            return

        audiourl = min(res.json()["item"]["audio"]["src"], key=self.priority, default=None)
        yield HTTP(copy.copy(self.config), audiourl, 128, output=self.output)

    def priority(self, line):
        if line.endswith("-hi"):
            return 0
        if line.endswith("-lo"):
            return 2
        return 1
