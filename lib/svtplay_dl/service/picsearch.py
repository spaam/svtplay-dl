# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.fetcher.rtmp import RTMP
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError
from svtplay_dl.utils.urllib import urlparse


class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ['dn.se', 'mobil.dn.se', 'di.se', 'csp.picsearch.com', 'csp.screen9.com']

    def get(self):
        if self.exclude():
            yield ServiceError("Excluding video")
            return

        ajax_auth = self.get_auth()
        if not ajax_auth:
            yield ServiceError("Cant find token for video")
            return

        mediaid = self.get_mediaid()
        if not mediaid:
            yield ServiceError("Cant find media id")
            return
        if not isinstance(mediaid, str):
            mediaid = mediaid.group(1)

        jsondata = self.http.request("get", "http://csp.picsearch.com/rest?jsonp=&eventParam=1&auth=%s&method=embed&mediaid=%s" % (ajax_auth.group(1), mediaid)).text
        jsondata = json.loads(jsondata)
        if "playerconfig" not in jsondata["media"]:
            yield ServiceError(jsondata["error"])
            return
        if "live" in jsondata["media"]["playerconfig"]["clip"]:
            self.options.live = jsondata["media"]["playerconfig"]["clip"]
        playlist = jsondata["media"]["playerconfig"]["playlist"][1]
        if "bitrates" in playlist:
            files = playlist["bitrates"]
            server = jsondata["media"]["playerconfig"]["plugins"]["bwcheck"]["netConnectionUrl"]

            for i in files:
                self.options.other = "-y '%s'" % i["url"]
                yield RTMP(copy.copy(self.options), server, i["height"])
        if "provider" in playlist:
            if playlist["provider"] != "rtmp":
                if "live" in playlist:
                    self.options.live = playlist["live"]
                if playlist["url"].endswith(".f4m"):
                    streams = hdsparse(self.options, self.http.request("get", playlist["url"], params={"hdcore": "3.7.0"}), playlist["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                if ".m3u8" in playlist["url"]:
                    streams = hlsparse(self.options, self.http.request("get", playlist["url"]), playlist["url"])
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]

    def get_auth(self):
        match = re.search(r"picsearch_ajax_auth[ ]*=[ ]*['\"]([^'\"]+)['\"]", self.get_urldata())
        if not match:
            match = re.search(r'screen9-ajax-auth="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('screen9"[ ]*:[ ]*"([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('s.src="(https://csp-ssl.picsearch.com[^"]+|http://csp.picsearch.com/rest[^"]+)', self.get_urldata())
            if match:
                data = self.http.request("get", match.group(1))
                match = re.search(r'ajaxAuth": "([^"]+)"', data.text)
            if not match:
                match = re.search('iframe src="(//csp.screen9.com[^"]+)"', self.get_urldata())
                if match:
                    url = "http:%s" % match.group(1)
                    data = self.http.request("get", url)
                    match = re.search(r"picsearch_ajax_auth = '([^']+)'", data.text)

        return match

    def get_mediaid(self):
        match = re.search(r"mediaId = '([^']+)';", self.get_urldata())
        if not match:
            match = re.search(r'media-id="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search(r'screen9-mid="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search(r'data-id="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('s.src="(https://csp-ssl.picsearch.com[^"]+|http://csp.picsearch.com/rest[^"]+)', self.get_urldata())
            if match:
                data = self.http.request("get", match.group(1))
                match = re.search(r'mediaid": "([^"]+)"', data.text)
            if not match:
                match = re.search('iframe src="(//csp.screen9.com[^"]+)"', self.get_urldata())
                if match:
                    url = "http:%s" % match.group(1)
                    data = self.http.request("get", url)
                    match = re.search(r"mediaid: '([^']+)'", data.text)
        if not match:
            urlp = urlparse(self.url)
            match = urlp.fragment
        return match
