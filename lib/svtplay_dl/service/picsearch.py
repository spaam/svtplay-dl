# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Picsearch(Service, OpenGraphThumbMixin):
    supported_domains = ["dn.se", "mobil.dn.se", "di.se", "csp.picsearch.com", "csp.screen9.com"]

    def get(self):
        self.backupapi = None

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

        jsondata = self.http.request(
            "get",
            "http://csp.screen9.com/player?eventParam=1&" "ajaxauth={}&method=embed&mediaid={}".format(ajax_auth.group(1), mediaid),
        ).text
        jsondata = json.loads(jsondata)

        if "data" in jsondata:
            if "live" in jsondata["data"]["publishing_status"]:
                self.config.set("live", jsondata["data"]["publishing_status"]["live"])
            playlist = jsondata["data"]["streams"]
            for i in playlist:
                if "application/x-mpegurl" in i:
                    streams = hlsparse(
                        self.config,
                        self.http.request("get", i["application/x-mpegurl"]),
                        i["application/x-mpegurl"],
                        output=self.output,
                    )
                    if streams:
                        for n in list(streams.keys()):
                            yield streams[n]
                if "video/mp4" in i:
                    yield HTTP(copy.copy(self.config), i["video/mp4"], 800, output=self.output)

        if self.backupapi:
            res = self.http.get(self.backupapi.replace("i=", ""), params={"i": "object"})
            data = res.text.replace("ps.embedHandler(", "").replace('"");', "")
            data = data[: data.rfind(",")]
            jansson = json.loads(data)
            for i in jansson["media"]["playerconfig"]["playlist"]:
                if "provider" in i and i["provider"] == "httpstreaming":
                    streams = hlsparse(self.config, self.http.request("get", i["url"]), i["url"], output=self.output)
                    for n in list(streams.keys()):
                        yield streams[n]

    def get_auth(self):
        match = re.search(r"picsearch_ajax_auth[ ]*=[ ]*['\"]([^'\"]+)['\"]", self.get_urldata())
        if not match:
            match = re.search(r'screen9-ajax-auth="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('screen9"[ ]*:[ ]*"([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('data-auth="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('s.src="(https://csp-ssl.picsearch.com[^"]+|http://csp.picsearch.com/rest[^"]+)', self.get_urldata())
            if match:
                data = self.http.request("get", match.group(1))
                self.backupapi = match.group(1)
                match = re.search(r'ajaxAuth": "([^"]+)"', data.text)
            if not match:
                match = re.search('iframe src="(//csp.screen9.com[^"]+)"', self.get_urldata())
                if match:
                    url = "http:{}".format(match.group(1))
                    data = self.http.request("get", url)
                    self.backupapi = url
                    match = re.search(r"picsearch_ajax_auth = '([^']+)'", data.text)
                    if not match:
                        match = re.search(r"screen9_ajax_auth = '([^']+)'", data.text)

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
            match = re.search(r"data-id=([^ ]+) ", self.get_urldata())
        if not match:
            match = re.search(r'data-videoid="([^"]+)"', self.get_urldata())
        if not match:
            match = re.search('s.src="(https://csp-ssl.picsearch.com[^"]+|http://csp.picsearch.com/rest[^"]+)', self.get_urldata())
            if match:
                data = self.http.request("get", match.group(1))
                match = re.search(r'mediaid": "([^"]+)"', data.text)
            if not match:
                match = re.search('iframe src="(//csp.screen9.com[^"]+)"', self.get_urldata())
                if match:
                    url = "http:{}".format(match.group(1))
                    data = self.http.request("get", url)
                    match = re.search(r"mediaid: '([^']+)'", data.text)
        if not match:
            urlp = urlparse(self.url)
            match = urlp.fragment
        return match
