# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
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
        match2 = re.search(r'data-audio-type="(\w+)"', data)
        if match and match2:
            aid = match.group(1)
            type = match2.group(1)
        else:
            yield ServiceError("Can't find audio info")
            return

        dataurl = f"https://sverigesradio.se/sida/playerajax/getaudiourl?id={aid}&type={type}&quality=high&format=iis"
        data = self.http.request("get", dataurl).text
        playerinfo = json.loads(data)
        yield HTTP(copy.copy(self.config), playerinfo["audioUrl"], 128, output=self.output)
