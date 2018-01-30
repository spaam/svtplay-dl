# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import os

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.utils import filenamify
from svtplay_dl.utils.urllib import urljoin, urlparse
from svtplay_dl.error import ServiceError


class Sportlib(Service, OpenGraphThumbMixin):
    supported_domains = ['sportlib.se']

    def get(self):
        data = self.http.get("https://www.sportlib.se/sportlib/login").text
        match = re.search('src="(/app[^"]+)">', data)
        if not match:
            yield ServiceError("Can't find url for login info")
            return

        url = urljoin("https://www.sportlib.se", match.group(1))
        data = self.http.get(url).text
        match = re.search('CLIENT_SECRET:"([^"]+)"', data)
        if not match:
            yield ServiceError("Cant fint login info")
            return
        cs = match.group(1)
        match = re.search('CLIENT_ID:"([^"]+)"', data)
        if not match:
            yield ServiceError("Cant fint login info")
            return
        cid = match.group(1)
        res = self.http.get("https://core.oz.com/channels?slug=sportlib&org=www.sportlib.se")
        janson = res.json()
        sid = janson["data"][0]["id"]

        data = {"client_id": cid, "client_secret": cs, "grant_type": "password",
                "username": self.options.username, "password": self.options.password}
        res = self.http.post("https://core.oz.com/oauth2/token?channelId={}".format(sid), data=data)
        if res.status_code > 200:
            yield ServiceError("Wrong username / password?")
            return
        janson = res.json()
        token_type = janson["token_type"].title()
        access_token = janson["access_token"]

        parse = urlparse(self.url)
        match = re.search("video/([-a-fA-F0-9]+)", parse.path)
        if not match:
            yield ServiceError("Cant find video id")
            return
        vid = match.group(1)

        headers = {"content-type": "application/json", "authorization": "{} {}".format(token_type, access_token)}
        url = "https://core.oz.com/channels/{}/videos/{}?include=collection,streamUrl".format(sid, vid)
        res = self.http.get(url, headers=headers)
        janson = res.json()
        cookiename = janson["data"]["streamUrl"]["cookieName"]
        token = janson["data"]["streamUrl"]["token"]
        hlsplaylist = janson["data"]["streamUrl"]["cdnUrl"]

        if self.options.output_auto:
            directory = os.path.dirname(self.options.output)
            title = filenamify(janson["data"]["title"])
            if len(directory):
                self.options.output = os.path.join(directory, title)
            else:
                self.options.output = title

        # get cookie
        postjson = {"name": cookiename, "value": token}
        res = self.http.post("https://playlist.oz.com/cookie", json=postjson)
        cookies = res.cookies
        streams = hlsparse(self.options, self.http.request("get", hlsplaylist), hlsplaylist, keycookie=cookies)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]
