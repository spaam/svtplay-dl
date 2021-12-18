# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103
import copy
import json
import logging
import re
from urllib.parse import quote_plus
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import Service


class TwitchException(Exception):
    pass


class TwitchUrlException(TwitchException):
    """
    Used to indicate an invalid URL for a given media_type. E.g.:

      TwitchUrlException('video', 'http://twitch.tv/example')
    """

    def __init__(self, media_type, url):
        super().__init__(f"'{url}' is not recognized as a {media_type} URL")


class Twitch(Service):
    # Twitch uses language subdomains, e.g. en.www.twitch.tv. They
    # are usually two characters, but may have a country suffix as well (e.g.
    # zh-tw, zh-cn and pt-br.
    supported_domains_re = [r"^(?:(?:[a-z]{2}-)?[a-z]{2}\.)?(www\.|clips\.)?twitch\.tv$"]

    api_base_url = "https://api.twitch.tv"
    hls_base_url = "http://usher.justin.tv/api/channel/hls"

    def get(self):
        urlp = urlparse(self.url)

        match = re.match(r"/(\w+)/([bcv])/(\d+)", urlp.path)
        if not match:
            if re.search("clips.twitch.tv", urlp.netloc):
                data = self._get_clips()
            else:
                data = self._get_channel(urlp)
        else:
            if match.group(2) in ["b", "c"]:
                yield ServiceError("This twitch video type is unsupported")
                return
            data = self._get_archive(match.group(3))
        try:
            yield from data
        except TwitchUrlException:
            yield ServiceError("This twitch video type is unsupported")
            return

    def _get_static_video(self, videoid):
        access = self._get_access_token(videoid)

        data = self.http.request("get", f"https://api.twitch.tv/kraken/videos/v{videoid}")
        if data.status_code == 404:
            yield ServiceError("Can't find the video")
            return
        info = json.loads(data.text)
        self.output["title"] = f"twitch-{info['channel']['name']}"
        self.output["episodename"] = info["title"]

        if "token" not in access:
            raise TwitchUrlException("video", self.url)
        nauth = quote_plus(str(access["token"]))
        authsig = access["sig"]

        url = f"http://usher.twitch.tv/vod/{videoid}?nauth={nauth}&nauthsig={authsig}"

        yield from hlsparse(copy.copy(self.config), self.http.request("get", url), url, output=self.output)

    def _get_archive(self, vid):
        try:
            yield from self._get_static_video(vid)
        except TwitchUrlException as e:
            logging.error(str(e))

    def _get_access_token(self, channel, vtype="vods"):
        """
        Get a Twitch access token. It's a three element dict:

         * mobile_restricted
         * sig
         * token

        `sig` is a hexadecimal string, and `token` is a JSON blob, with
        information about access expiration. `mobile_restricted` is not
        important, but is a boolean.

        Both `sig` and `token` should be added to the HLS URI, and the
        token should, of course, be URI encoded.
        """
        return self._ajax_get(f"/api/{vtype}/{channel}/access_token")

    def _ajax_get(self, method):
        url = f"{self.api_base_url}/{method}"

        # Logic found in Twitch's global.js. Prepend /kraken/ to url
        # path unless the API method already is absolute.
        if method[0] != "/":
            method = f"/kraken/{method}"

        payload = self.http.request("get", url)
        return json.loads(payload.text)

    def _get_hls_url(self, channel):
        access = self._get_access_token(channel, "channels")

        query = f"token={quote_plus(access['token'])}&sig={access['sig']}&allow_source=true&allow_spectre=true"
        return f"{self.hls_base_url}/{channel}.m3u8?{query}"

    def _get_channel(self, urlp):
        match = re.match(r"/(\w+)", urlp.path)

        if not match:
            raise TwitchUrlException("channel", urlp.geturl())

        channel = match.group(1)

        self.output["title"] = channel

        hls_url = self._get_hls_url(channel)
        urlp = urlparse(hls_url)

        self.config.set("live", True)
        data = self.http.request("get", hls_url)
        if data.status_code == 404:
            yield ServiceError("Stream is not online.")
            return
        yield from hlsparse(self.output, data, hls_url, output=self.output)

    def _get_clips(self):
        match = re.search(r"quality_options: (\[[^\]]+\])", self.get_urldata())
        if not match:
            yield ServiceError("Can't find the video clip")
            return
        name = re.search(r'slug: "([^"]+)"', self.get_urldata()).group(1)
        brodcaster = re.search('broadcaster_login: "([^"]+)"', self.get_urldata()).group(1)
        self.output["title"] = f"twitch-{brodcaster}"
        self.output["episodename"] = name

        dataj = json.loads(match.group(1))
        for i in dataj:
            yield HTTP(copy.copy(self.config), i["source"], i["quality"], output=self.output)
