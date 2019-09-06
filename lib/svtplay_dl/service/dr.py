# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import

import base64
import binascii
import copy
import hashlib
import json
import re
from urllib.parse import urljoin
from urllib.parse import urlparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import modes
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hds import hdsparse
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service
from svtplay_dl.subtitle import subtitle


class Dr(Service, OpenGraphThumbMixin):
    supported_domains = ["dr.dk"]

    def get(self):
        data = self.get_urldata()

        match = re.search(r'resource:[ ]*"([^"]*)",', data)
        if match:
            resource_url = match.group(1)
            resource_data = self.http.request("get", resource_url).content
            resource = json.loads(resource_data)
            streams = self.find_stream(self.config, resource)
            yield from streams
        else:
            match = re.search(r'resource="([^"]*)"', data)
            if not match:
                yield ServiceError("Cant find resource info for this video")
                return
            if match.group(1)[:4] != "http":
                resource_url = "http:{}".format(match.group(1))
            else:
                resource_url = match.group(1)
            resource_data = self.http.request("get", resource_url).text
            resource = json.loads(resource_data)

            if "Links" not in resource:
                yield ServiceError("Cant access this video. its geoblocked.")
                return
            if "SubtitlesList" in resource and len(resource["SubtitlesList"]) > 0:
                suburl = resource["SubtitlesList"][0]["Uri"]
                yield subtitle(copy.copy(self.config), "wrst", suburl, output=self.output)
            if "Data" in resource:
                streams = self.find_stream(self.config, resource)
                yield from streams
            else:
                for stream in resource["Links"]:
                    uri = stream["Uri"]
                    if uri is None:
                        uri = self._decrypt(stream["EncryptedUri"])

                    if stream["Target"] == "HDS":
                        streams = hdsparse(copy.copy(self.config), self.http.request("get", uri, params={"hdcore": "3.7.0"}), uri, output=self.output)
                        if streams:
                            for n in list(streams.keys()):
                                yield streams[n]
                    if stream["Target"] == "HLS":
                        streams = hlsparse(self.config, self.http.request("get", uri), uri, output=self.output)
                        for n in list(streams.keys()):
                            yield streams[n]

    def find_all_episodes(self, config):
        episodes = []
        matches = re.findall(r'<button class="show-more" data-url="([^"]+)" data-partial="([^"]+)"', self.get_urldata())
        for encpath, enccomp in matches:
            newstyle = "_" in encpath
            if newstyle:
                encbasepath = encpath.split("_")[0]
                path = base64.b64decode(encbasepath + "===").decode("latin1")
            else:
                path = base64.b64decode(encpath + "===").decode("latin1")

            if "/view/" in path:
                continue

            params = "offset=0&limit=1000"
            if newstyle:
                encparams = base64.b64encode(params.encode("latin1")).decode("latin1").rstrip("=")
                encpath = "{}_{}".format(encbasepath, encparams)
            else:
                path = "{}?{}".format(urlparse(path).path, params)
                encpath = base64.b64encode(path.encode("latin1")).decode("latin1").rstrip("=")

            url = urljoin("https://www.dr.dk/tv/partial/", "{}/{}".format(enccomp, encpath))
            data = self.http.request("get", url).content.decode("latin1")

            matches = re.findall(r'"program-link" href="([^"]+)">', data)
            episodes = [urljoin("https://www.dr.dk/", url) for url in matches]
            break

        if not episodes:
            prefix = "/".join(urlparse(self.url).path.rstrip("/").split("/")[:-1])
            matches = re.findall(r'"program-link" href="([^"]+)">', self.get_urldata())
            episodes = [urljoin("https://www.dr.dk/", url) for url in matches if url.startswith(prefix)]

        if config.get("all_last") != -1:
            episodes = episodes[: config.get("all_last")]
        else:
            episodes.reverse()

        return episodes

    def find_stream(self, config, resource):
        tempresource = resource["Data"][0]["Assets"]
        # To find the VideoResource, they have Images as well
        for resources in tempresource:
            if resources["Kind"] == "VideoResource":
                links = resources["Links"]
                break
        for i in links:
            if i["Target"] == "Ios" or i["Target"] == "HLS":
                streams = hlsparse(config, self.http.request("get", i["Uri"]), i["Uri"], output=self.output)
                for n in list(streams.keys()):
                    yield streams[n]

    def _decrypt(self, url):
        n = int(url[2:10], 16)
        iv_hex = url[10 + n :]
        data = binascii.a2b_hex(url[10 : 10 + n].encode("ascii"))
        key = hashlib.sha256(("%s:sRBzYNXBzkKgnjj8pGtkACch" % iv_hex).encode("utf-8")).digest()
        iv = bytes.fromhex(iv_hex)

        backend = default_backend()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(data)
        return decrypted[: -decrypted[-1]].decode("utf-8")
