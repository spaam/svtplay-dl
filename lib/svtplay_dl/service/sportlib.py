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

        res = self.http.get("https://core.oz.com/channels?slug=sportlib&org=www.sportlib.se")
        janson = res.json()
        sid = janson["data"][0]["id"]

        res = self.http.post(
            f"https://core.oz.com/oauth2/token?channelId={sid}",
            data={
                "client_id": match.group(1),
                "client_secret": cs,
                "grant_type": "password",
                "username": self.config.get("username"),
                "password": self.config.get("password"),
            },
        )
        if res.status_code > 200:
            yield ServiceError("Wrong username / password?")
            return
        janson = res.json()
        parse = urlparse(self.url)
        match = re.search("video/([-a-fA-F0-9]+)", parse.path)
        if not match:
            yield ServiceError("Cant find video id")
            return

        url = f"https://core.oz.com/channels/{sid}/videos/{match.group(1)}?include=collection,streamUrl"
        res = self.http.get(
            url,
            headers={"content-type": "application/json", "authorization": f"{janson['token_type'].title()} {janson['access_token']}"},
        )
        janson = res.json()

        self.output["title"] = janson["data"]["title"]

        # get cookie
        postjson = {"name": janson["data"]["streamUrl"]["cookieName"], "value": janson["data"]["streamUrl"]["token"]}
        res = self.http.post("https://playlist.oz.com/cookie", json=postjson)
        cookies = res.cookies
        yield from hlsparse(
            self.config,
            self.http.request("get", janson["data"]["streamUrl"]["cdnUrl"]),
            janson["data"]["streamUrl"]["cdnUrl"],
            keycookie=cookies,
            output=self.output,
        )
