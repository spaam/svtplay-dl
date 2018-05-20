# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import json
import os
import re

from svtplay_dl.service import Service
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.utils import filenamify


class Npo(Service):
    supported_domains = ["npo.nl", "ntr.nl", "omroepwnl.nl", "zapp.nl", "npo3.nl"]

    def get(self):
        # Get video id
        parse = urlparse(self.url)
        video_id = parse.path.split("/")[-1]

        if "__" in video_id:
            video_id = video_id.split("__")[-1]

        if not video_id:
            yield ServiceError("Can't find video info")
            return

        # Get prid
        prid_src = self.http.request("get", "http://e.omroep.nl/metadata/{0}".format(video_id))
        prid_raw = prid_src.text.split('(', 1)[-1].split(')', 1)[0]

        try:
            janson = json.loads(prid_raw)
            prid = janson["prid"]

            if "titel" in janson:
                directory = os.path.dirname(self.options.output)
                title = filenamify(janson["titel"])
                self.options.output = os.path.join(directory, title)

        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode prid request: {0}".format(prid_raw))
            return

        # Get token
        token_src = self.http.request("get", "http://ida.omroep.nl/app.php/auth/{0}".format(prid))

        try:
            janson = json.loads(token_src.text)
            token = janson["token"]

        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode token request: {0}".format(token_src.text))
            return

        # Get super api
        api_url = self.http.request("get", "http://ida.omroep.nl/app.php/{0}?token={1}".format(prid, token))

        try:
            janson = json.loads(api_url.text)

        except json.decoder.JSONDecodeError:
            yield ServiceError("Can't decode api request: {0}".format(api_url.text))
            return

        # Get sub api and streams
        for item in janson["items"][0]:

            stream = None

            if item["format"] == "hls":
                api = self.http.request("get", item["url"]).text
                raw_url = re.search(r'"url":"(.+?)"', api).group(1)
                url = json.loads('"{0}"'.format(raw_url))

                stream = hlsparse(self.options, self.http.request("get", url), url, output=self.output)

            if stream:
                for key in list(stream.keys()):
                    yield stream[key]
