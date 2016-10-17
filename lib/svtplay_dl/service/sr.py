# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import json
import re
import copy

from svtplay_dl.utils.urllib import urljoin
from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Sr(Service, OpenGraphThumbMixin):
    supported_domains = ['sverigesradio.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search('data-audio-type="publication" data-audio-id="(\d+)">', data)  # Nyheter
        if match:
            dataurl = "https://sverigesradio.se/sida/playerajax/getaudiourl?id={}&type={}&quality=high&format=iis".format(match.group(1), "publication")
            data = self.http.request("get", dataurl).text
            playerinfo = json.loads(data)
            yield HTTP(copy.copy(self.options), playerinfo["audioUrl"], 128)
            return
        match = re.search(r'href="(/topsy/ljudfil/\d+-mp3)"', data)  # Ladda ner
        if match:
            yield HTTP(copy.copy(self.options), urljoin("https://sverigesradio.se", match.group(1)), 128)
            return
        else:
            match = re.search('data-audio-type="secondary" data-audio-id="(\d+)"', data) # Ladda ner utan musik
            match2 = re.search('data-audio-type="episode" data-audio-id="(\d+)"', data) # Ladda ner med musik
            if match:
                aid = match.group(1)
                type = "secondary"
            elif match2:
                aid = match2.group(1)
                type = "episode"
            else:
                yield ServiceError("Can't find audio info")
                return

        dataurl = "https://sverigesradio.se/sida/playerajax/getaudiourl?id={}&type={}&quality=high&format=iis".format(aid, type)
        data = self.http.request("get", dataurl).text
        playerinfo = json.loads(data)
        yield HTTP(copy.copy(self.options), playerinfo["audioUrl"], 128)


