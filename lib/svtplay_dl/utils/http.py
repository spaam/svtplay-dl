import http.client
import logging
import re
from html import unescape
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter
from requests.adapters import Retry
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.parser import Options

http.client._MAXHEADERS = 200

# Used for UA spoofing in get_http_data()
FIREFOX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"

retry = Retry(total=5, read=5, connect=5, backoff_factor=0.3, status_forcelist=(500, 502, 504))


class HTTP(Session):
    def __init__(self, config={}, *args, **kwargs):
        Session.__init__(self, *args, **kwargs)
        adapter = HTTPAdapter(max_retries=retry)

        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self.verify = config.get("ssl_verify")
        self.proxy = config.get("proxy")
        if config.get("http_headers"):
            self.headers.update(self.split_header(config.get("http_headers")))
        if config.get("cookies"):
            self.cookies.update(self.split_header(config.get("cookies")))
        self.headers.update({"User-Agent": FIREFOX_UA})

    def check_redirect(self, url):
        return self.get(url, stream=True).url

    def request(self, method, url, *args, **kwargs):
        headers = kwargs.pop("headers", None)
        if headers:
            for i in headers.keys():
                self.headers[i] = headers[i]
        logging.debug("HTTP getting %r", url)
        res = Session.request(self, method, url, verify=self.verify, proxies=self.proxy, *args, **kwargs)
        return res

    def split_header(self, headers):
        return dict(x.split("=") for x in headers.split(";") if x)


def download_thumbnails(output, config, urls):
    for show, url in urls:
        if "&amp;" in url:
            url = unescape(url)
        data = Session().get(url).content
        loutout = output.copy()
        loutout["ext"] = "tbn"
        if show:
            # Config for downloading show thumbnail
            cconfig = Options()
            cconfig.set("output", config.get("output"))
            cconfig.set("path", config.get("path"))
            cconfig.set("subfolder", config.get("subfolder"))
            cconfig.set("filename", "{title}.tvshow.{ext}")
        else:
            cconfig = config

        filename = formatname(loutout, cconfig)
        logging.info("Thumbnail: %s", filename)

        with open(filename, "wb") as fd:
            fd.write(data)


def get_full_url(url, srcurl):
    if url[:4] == "http":
        return url
    if url[0] == "/":
        baseurl = re.search(r"^(http[s]{0,1}://[^/]+)/", srcurl)
        return f"{baseurl.group(1)}{url}"

    # remove everything after last / in the path of the URL
    baseurl = re.sub(r"^([^\?]+)/[^/]*(\?.*)?$", r"\1/", srcurl)
    returl = urljoin(baseurl, url)

    return returl
