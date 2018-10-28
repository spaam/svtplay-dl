# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import re
import json
import copy
from urllib.parse import urlparse, quote_plus

from svtplay_dl.service import Service
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class TwitchException(Exception):
    pass


class TwitchUrlException(TwitchException):
    """
    Used to indicate an invalid URL for a given media_type. E.g.:

      TwitchUrlException('video', 'http://twitch.tv/example')
    """
    def __init__(self, media_type, url):
        super(TwitchUrlException, self).__init__(
            "'{0}' is not recognized as a {1} URL".format(url, media_type)
        )


class Twitch(Service):
    # Twitch uses language subdomains, e.g. en.www.twitch.tv. They
    # are usually two characters, but may have a country suffix as well (e.g.
    # zh-tw, zh-cn and pt-br.
    supported_domains_re = [
        r'^(?:(?:[a-z]{2}-)?[a-z]{2}\.)?(www\.|clips\.)?twitch\.tv$',
    ]

    api_base_url = 'https://api.twitch.tv'
    hls_base_url = 'http://usher.justin.tv/api/channel/hls'

    def get(self):
        urlp = urlparse(self.url)

        match = re.match(r'/(\w+)/([bcv])/(\d+)', urlp.path)
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
            for i in data:
                yield i
        except TwitchUrlException:
            yield ServiceError("This twitch video type is unsupported")
            return

    def _get_static_video(self, videoid):
        access = self._get_access_token(videoid)

        data = self.http.request("get", "https://api.twitch.tv/kraken/videos/v{0}".format(videoid))
        if data.status_code == 404:
            yield ServiceError("Can't find the video")
            return
        info = json.loads(data.text)
        self.output["title"] = "twitch-{0}".format(info["channel"]["name"])
        self.output["episodename"] = info["title"]

        if "token" not in access:
            raise TwitchUrlException('video', self.url)
        nauth = quote_plus(str(access["token"]))
        authsig = access["sig"]

        url = "http://usher.twitch.tv/vod/{0}?nauth={1}&nauthsig={2}".format(videoid, nauth, authsig)

        streams = hlsparse(copy.copy(self.config), self.http.request("get", url), url, output=self.output)
        if streams:
            for n in list(streams.keys()):
                yield streams[n]

    def _get_archive(self, vid):
        try:
            for n in self._get_static_video(vid):
                yield n
        except TwitchUrlException as e:
            log.error(str(e))

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
        return self._ajax_get('/api/{0}/{1}/access_token'.format(vtype, channel))

    def _ajax_get(self, method):
        url = "{0}/{1}".format(self.api_base_url, method)

        # Logic found in Twitch's global.js. Prepend /kraken/ to url
        # path unless the API method already is absolute.
        if method[0] != '/':
            method = '/kraken/{0}'.format(method)

        payload = self.http.request("get", url)
        return json.loads(payload.text)

    def _get_hls_url(self, channel):
        access = self._get_access_token(channel, "channels")

        query = "token={0}&sig={1}&allow_source=true&allow_spectre=true".format(quote_plus(access['token']), access['sig'])
        return "{0}/{1}.m3u8?{2}".format(self.hls_base_url, channel, query)

    def _get_channel(self, urlp):
        match = re.match(r'/(\w+)', urlp.path)

        if not match:
            raise TwitchUrlException('channel', urlp.geturl())

        channel = match.group(1)

        self.output["title"] = channel

        hls_url = self._get_hls_url(channel)
        urlp = urlparse(hls_url)

        self.config.set("live", True)
        data = self.http.request("get", hls_url)
        if data.status_code == 404:
            yield ServiceError("Stream is not online.")
            return
        streams = hlsparse(self.output, data, hls_url, output=self.output)
        for n in list(streams.keys()):
            yield streams[n]

    def _get_clips(self):
        match = re.search(r"quality_options: (\[[^\]]+\])", self.get_urldata())
        if not match:
            yield ServiceError("Can't find the video clip")
            return
        name = re.search(r'slug: "([^"]+)"', self.get_urldata()).group(1)
        brodcaster = re.search('broadcaster_login: "([^"]+)"', self.get_urldata()).group(1)
        self.output["title"] = "twitch-{0}".format(brodcaster)
        self.output["episodename"] = name

        dataj = json.loads(match.group(1))
        for i in dataj:
            yield HTTP(copy.copy(self.config), i["source"], i["quality"], output=self.output)
