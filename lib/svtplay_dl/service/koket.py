# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals
from urllib.parse import urlparse

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError


class Koket(Service, OpenGraphThumbMixin):
    supported_domains = ['koket.se']
    supported_path = "/kurser"

    def get(self):
        urlp = urlparse(self.url)
        slugs = urlp.path.split('/')

        courseSlug = slugs[2]
        lessonSlug = slugs[3]

        login = self._login()
        if not login:
            yield ServiceError("Could not login")
            return

        auth_token = self._getAuthToken()
        authDataRes = self.http.get("https://www.koket.se/kurser/api/data/{}".format(auth_token))

        authDataJson = authDataRes.json()

        courses = authDataJson["content"]["coursePages"]
        for c in courses:
            if c["slug"] == courseSlug:
                course = c

        if not course:
            yield ServiceError("Could not find course")
            return

        lessons = course["lessons"]
        for l in lessons:
            if l["slug"] == lessonSlug:
                lesson = l

        if not lesson:
            yield ServiceError("Could not find lesson")
            return

        self.output["id"] = lesson["videoAssetId"]
        self.output["title"] = lesson["title"]

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"])

        videoDataRes = self.http.request("get", url, cookies=self.cookies)
        if videoDataRes.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(self.config, self.http.request("get", videoDataRes.json()["playbackItem"]["manifestUrl"]),
                               videoDataRes.json()["playbackItem"]["manifestUrl"], output=self.output)
            for n in list(streams.keys()):
                yield streams[n]

    def _login(self):
        username = self.config.get("username")
        password = self.config.get("password")

        if (not username) or (not password):
            return False

        url = "https://www.koket.se/account/login"
        login = {
            "username": self.config.get("username"),
            "password": self.config.get("password")
        }

        self.http.get(url)
        self.http.post(url, data=login)

        if self._getAuthToken() is None:
            return False

        return True

    def _getAuthToken(self):
        return self.http.cookies.get("authToken")
