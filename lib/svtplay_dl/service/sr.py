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

        matches = re.finditer(r'data-audio-id="(\d+)"', data)
        matches2 = re.finditer(r'data-audio-type="(\w+)"', data)
        streams = [(match.group(1), match2.group(1)) for match, match2 in zip(matches, matches2)]
        if not streams:
            yield ServiceError("Can't find audio info")
            return

        # Filter on first audio id
        aid = streams[0][0]
        streams = sorted({stream for stream in streams if stream[0] == aid})


        for aid, type in streams:
            dataurl = f"https://sverigesradio.se/sida/playerajax/getaudiourl?id={aid}&type={type}&quality=high&format=iis"
            data = self.http.request("get", dataurl).text
            playerinfo = json.loads(data)
            language = "med-musik" if type == "secondary" else "utan-musik"
            yield HTTP(copy.copy(self.config), playerinfo["audioUrl"], 128, output=self.output, language=language)
