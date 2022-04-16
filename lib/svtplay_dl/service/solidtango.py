# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.dash import dashparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Solidtango(Service):
    supported_domains_re = [r"^([^.]+\.)*solidtango.com"]
    supported_domains = ["mm-resource-service.herokuapp.com", "solidtango.com", "solidsport.com"]

    def get(self):
        data = self.get_urldata()
        parse = urlparse(self.url)
        if "solidsport" in parse.netloc:
            if self.config.get("username") and self.config.get("password"):
                self.http.request("get", "https://solidsport.com/login")
                pdata = {
                    "username": self.config.get("username"),
                    "password": self.config.get("password"),
                }
                res = self.http.request("post", "https://solidsport.com/api/play_v1/session/auth", json=pdata)
                if res.status_code > 400:
                    yield ServiceError("Wrong username or password")
                    return

                auth_token = res.json()["token"]
                slug = parse.path[parse.path.rfind("/") + 1 :]
                company = re.search(r"/([^\/]+)/", parse.path).group(1)
                url = f"https://solidsport.com/api/play_v1/media_object/watch?company={company}&"
                if "/watch/" in self.url:
                    url += f"media_object_slug={slug}"
                elif "/games/" in self.url:
                    url += f"game_ident={slug}"
                res = self.http.request("get", url, headers={"Authorization": f"Bearer {auth_token}"})
                videoid = res.json()["id"]
                self.output["title"] = res.json()["title"]
                self.output["id"] = res.json()["id"]
                url = f"https://solidsport.com/api/play_v1/media_object/{videoid}/request_stream_urls?admin_access=false&company={company}"
                res = self.http.request("get", url, headers={"Authorization": f"Bearer {auth_token}"})
                if "dash" in res.json()["urls"]:
                    yield from dashparse(self.config, self.http.request("get", res.json()["urls"]["dash"]), res.json()["urls"]["dash"], self.output)
                if "hls" in res.json()["urls"]:
                    yield from hlsparse(self.config, self.http.request("get", res.json()["urls"]["hls"]), res.json()["urls"]["hls"], self.output)
                return

        match = re.search('src="(http://mm-resource-service.herokuapp.com[^"]*)"', data)
        if match:
            data = self.http.request("get", match.group(1)).text
            match = re.search('src="(https://[^"]+solidtango[^"]+)" ', data)
            if match:
                data = self.http.request("get", match.group(1)).text
        match = re.search(r"<title>(http[^<]+)</title>", data)
        if match:
            data = self.http.request("get", match.group(1)).text

        match = re.search("is_livestream: true", data)
        if match:
            self.config.set("live", True)
        match = re.search("isLivestream: true", data)
        if match:
            self.config.set("live", True)
        match = re.search('html5_source: "([^"]+)"', data)
        match2 = re.search('hlsURI: "([^"]+)"', data)
        if match:
            yield from hlsparse(self.config, self.http.request("get", match.group(1)), match.group(1), output=self.output)
        elif match2:
            yield from hlsparse(self.config, self.http.request("get", match2.group(1)), match2.group(1), output=self.output)
        else:
            parse = urlparse(self.url)
            url2 = f"https://{parse.netloc}/api/v1/play/{parse.path[parse.path.rfind('/') + 1 :]}.xml"
            data = self.http.request("get", url2)
            if data.status_code != 200:
                yield ServiceError("Can't find video info. if there is a video on the page. its a bug.")
                return
            xmldoc = data.text
            xml = ET.XML(xmldoc)
            elements = xml.findall(".//manifest")
            yield from hlsparse(self.config, self.http.request("get", elements[0].text), elements[0].text, output=self.output)
