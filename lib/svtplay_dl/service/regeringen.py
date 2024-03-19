import html
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.service import Service


class Regeringen(Service):
    supported_domains_re = ["regeringen.se", "www.regeringen.se"]

    def get(self):
        res = self.http.get(self.url)
        html_data = res.text

        match = re.search(r"<title>(.*?) -", html_data)
        if match:
            self.output["title"] = html.unescape(match.group(1))

        match = re.search(r"//video.qbrick.com/api/v1/(.*?)'", html_data)
        if match:
            result = match.group(1)
        else:
            yield ServiceError("Cant find the video.")

        data_url = f"https://video.qbrick.com/api/v1/{result}"

        res = self.http.get(data_url)
        data = res.json()
        resources = data["asset"]["resources"]
        index_resources = [resource for resource in resources if resource["type"] == "index"]
        links = index_resources[0]["renditions"][0]["links"]
        hls_url = [link for link in links if "x-mpegURL" in link["mimeType"]][0]["href"]

        if hls_url.find(".m3u8") > 0:
            yield from hlsparse(self.config, self.http.request("get", hls_url), hls_url, output=self.output)
