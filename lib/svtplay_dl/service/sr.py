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
        else:
            yield ServiceError("Can't find audio info")
            return

        for what in ["episode", "secondary"]:
            language = ""
            apiurl = f"https://sverigesradio.se/playerajax/audio?id={aid}&type={what}&publicationid={pubid}&quality=high"
            resp = self.http.request("get", apiurl)
            if resp.status_code > 400:
                continue
            playerinfo = resp.json()
            if what == "secondary":
                language = "musik"
            yield HTTP(copy.copy(self.config), playerinfo["audioUrl"], 128, output=self.output, language=language)
