# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# pylint has issues with urlparse: "some types could not be inferred"
# pylint: disable=E1103

from __future__ import absolute_import
import sys
import re
import json
import xml.etree.ElementTree as ET

from svtplay_dl.utils.urllib import urlparse, quote
from svtplay_dl.service import Service
from svtplay_dl.utils import get_http_data
from svtplay_dl.log import log
from svtplay_dl.fetcher.hls import download_hls
from svtplay_dl.fetcher.http import download_http

class JustinException(Exception):
    pass

class JustinUrlException(JustinException):
    """
    Used to indicate an invalid URL for a given media_type. E.g.:

      JustinUrlException('video', 'http://twitch.tv/example')
    """
    def __init__(self, media_type, url):
        super(JustinUrlException, self).__init__(
            "'%s' is not recognized as a %s URL" % (url, media_type)
        )


class Justin(Service):
    # Justin and Twitch uses language subdomains, e.g. en.www.twitch.tv. They
    # are usually two characters, but may have a country suffix as well (e.g.
    # zh-tw, zh-cn and pt-br.
    supported_domains_re = [
        r'^(?:(?:[a-z]{2}-)?[a-z]{2}\.)?(www\.)?twitch\.tv$',
        r'^(?:(?:[a-z]{2}-)?[a-z]{2}\.)?(www\.)?justin\.tv$']

    # TODO: verify that this will support Justin as well
    api_base_url = 'https://api.twitch.tv'
    hls_base_url = 'http://usher.justin.tv/api/channel/hls'

    def get(self, options):
        urlp = urlparse(self.url)
        success = False

        for jtv_video_type in [self._get_chapter, self._get_archive,
                               self._get_channel]:
            try:
                jtv_video_type(urlp, options)
                success = True
                break
            except JustinUrlException as e:
                log.debug(str(e))

        if not success:
            log.debug(str(e))
            log.error("This twitch/justin video type is unsupported")
            sys.exit(2)


    def _get_static_video(self, vid, options, vidtype):
        url = "http://api.justin.tv/api/broadcast/by_%s/%s.xml?onsite=true" % (
            vidtype, vid)
        data = get_http_data(url)
        if not data:
            return False

        xml = ET.XML(data)
        url = xml.find("archive").find("video_file_url").text

        download_http(options, url)


    def _get_archive(self, urlp, options):
        match = re.match(r'/\w+/b/(\d+)', urlp.path)
        if not match:
            raise JustinUrlException('video', urlp.geturl())

        self._get_static_video(match.group(1), options, 'archive')


    def _get_chapter(self, urlp, options):
        match = re.match(r'/\w+/c/(\d+)', urlp.path)
        if not match:
            raise JustinUrlException('video', urlp.geturl())

        self._get_static_video(match.group(1), options, 'chapter')


    def _get_access_token(self, channel):
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
        return self._ajax_get('/api/channels/%s/access_token' % channel)


    def _ajax_get(self, method):
        url = "%s/%s" % (self.api_base_url, method)

        # Logic found in Twitch's global.js. Prepend /kraken/ to url
        # path unless the API method already is absolute.
        if method[0] != '/':
            method = '/kraken/%s' % method

        # There are references to a api_token in global.js; it's used
        # with the "Twitch-Api-Token" HTTP header. But it doesn't seem
        # to be necessary.
        payload = get_http_data(url, header={
            'Accept': 'application/vnd.twitchtv.v2+json'
        })
        return json.loads(payload)


    def _get_hls_url(self, channel):
        access = self._get_access_token(channel)

        query = "token=%s&sig=%s" % (quote(access['token']), access['sig'])
        return "%s/%s.m3u8?%s" % (self.hls_base_url, channel, query)


    def _get_channel(self, urlp, options):
        match = re.match(r'/(\w+)', urlp.path)

        if not match:
            raise JustinUrlException('channel', urlp.geturl())

        channel = match.group(1)
        hls_url = self._get_hls_url(channel)
        urlp = urlparse(hls_url)

        options.live = True
        if not options.output:
            options.output = channel

        download_hls(options, hls_url)
