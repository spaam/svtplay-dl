# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


def findCourse(data, courseSlug):
    for c in data["content"]["coursePages"]:
        if c["slug"] == courseSlug:
            return c
    return None


def findLesson(course, lessonSlug):
    for l in course["lessons"]:
        if l["slug"] == lessonSlug:
            return l
    return None


class Koket(Service, OpenGraphThumbMixin):
    supported_domains = ["koket.se"]
    supported_path = "/kurser"

    def __init__(self, config, _url, http=None):
        Service.__init__(self, config, _url, http)
        self._data = None

    def get(self):
        urlp = urlparse(self.url)
        slugs = urlp.path.split("/")

        courseSlug = slugs[2]
        lessonSlug = slugs[3]

        login = self._login()
        if not login:
            yield ServiceError("Could not login")
            return

        data = self._getData()
        if data is None:
            yield ServiceError("Could not fetch data")
            return

        course = findCourse(data, courseSlug)

        if course is None:
            yield ServiceError("Could not find course")
            return

        lesson = findLesson(course, lessonSlug)

        if lesson is None:
            yield ServiceError("Could not find lesson")
            return

        self.output["id"] = lesson["videoAssetId"]
        self.output["title"] = lesson["title"]

        url = "https://playback-api.b17g.net/media/{}?service=tv4&device=browser&protocol=hls%2Cdash&drm=widevine".format(self.output["id"])

        videoDataRes = self.http.get(url)
        if videoDataRes.json()["playbackItem"]["type"] == "hls":
            streams = hlsparse(
                self.config,
                self.http.get(videoDataRes.json()["playbackItem"]["manifestUrl"]),
                videoDataRes.json()["playbackItem"]["manifestUrl"],
                output=self.output,
            )
            for n in list(streams.keys()):
                yield streams[n]

    def _login(self):
        if self._getAuthToken() is None:
            username = self.config.get("username")
            password = self.config.get("password")

            if (not username) or (not password):
                return False

            url = "https://www.koket.se/account/login"
            login = {"username": username, "password": password}

            self.http.get(url)
            self.http.post(url, data=login)

        if self._getAuthToken() is None:
            return False

        return True

    def _getAuthToken(self):
        return self.http.cookies.get("authToken")

    def _getData(self):
        auth_token = self._getAuthToken()
        if auth_token is None:
            return None

        if self._data is None:
            self._data = self.http.get(f"https://www.koket.se/kurser/api/data/{auth_token}").json()

        return self._data
