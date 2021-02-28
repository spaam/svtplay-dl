# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import re
from urllib.parse import urljoin
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Sportlib(Service, OpenGraphThumbMixin):
    supported_domains = ["sportlib.se"]

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

        data = {
            "client_id": cid,
            "client_secret": cs,
            "grant_type": "password",
            "username": self.config.get("username"),
            "password": self.config.get("password"),
        }
        res = self.http.post(f"https://core.oz.com/oauth2/token?channelId={sid}", data=data)
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

        headers = {"content-type": "application/json", "authorization": f"{token_type} {access_token}"}
        url = f"https://core.oz.com/channels/{sid}/videos/{vid}?include=collection,streamUrl"
        res = self.http.get(url, headers=headers)
        janson = res.json()
        cookiename = janson["data"]["streamUrl"]["cookieName"]
        token = janson["data"]["streamUrl"]["token"]
        hlsplaylist = janson["data"]["streamUrl"]["cdnUrl"]

        self.output["title"] = janson["data"]["title"]

        # get cookie
        postjson = {"name": cookiename, "value": token}
        res = self.http.post("https://playlist.oz.com/cookie", json=postjson)
        cookies = res.cookies
        streams = hlsparse(self.config, self.http.request("get", hlsplaylist), hlsplaylist, keycookie=cookies, output=self.output)
        for n in list(streams.keys()):
            yield streams[n]
