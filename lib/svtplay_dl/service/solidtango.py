# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import xml.etree.ElementTree as ET

from svtplay_dl.service import Service
from svtplay_dl.fetcher.hls import hlsparse
from svtplay_dl.error import ServiceError
from svtplay_dl.utils.urllib import urlparse
from svtplay_dl.utils import is_py2


class Solidtango(Service):
    supported_domains_re = [r'^([^.]+\.)*solidtango.com']
    supported_domains = ['mm-resource-service.herokuapp.com', 'solidtango.com']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return
        match = re.search('src="(http://mm-resource-service.herokuapp.com[^"]*)"', data)
        if match:
            data = self.http.request("get", match.group(1)).text
            match = re.search('src="(https://[^"]+solidtango[^"]+)" ', data)
            if match:
                data = self.http.request("get", match.group(1)).text
        match = re.search(r'<title>(http[^<]+)</title>', data)
        if match:
            data = self.http.request("get", match.group(1)).text

        match = re.search('is_livestream: true', data)
        if match:
            self.options.live = True
        match = re.search('isLivestream: true', data)
        if match:
            self.options.live = True
        match = re.search('html5_source: "([^"]+)"', data)
        match2 = re.search('hlsURI: "([^"]+)"', data)
        if match:
            streams = hlsparse(self.options, self.http.request("get", match.group(1)), match.group(1))
            for n in list(streams.keys()):
                yield streams[n]
        elif match2:
            streams = hlsparse(self.options, self.http.request("get", match2.group(1)), match2.group(1))
            for n in list(streams.keys()):
                yield streams[n]
        else:
            parse = urlparse(self.url)
            url2 = "https://{0}/api/v1/play/{1}.xml".format(parse.netloc, parse.path[parse.path.rfind("/") + 1:])
            data = self.http.request("get", url2)
            if data.status_code != 200:
                yield ServiceError("Can't find video info. if there is a video on the page. its a bug.")
                return
            xmldoc = data.text
            if is_py2 and isinstance(xmldoc, unicode):
                xmldoc = xmldoc.encode("utf8")
            xml = ET.XML(xmldoc)
            elements = xml.findall(".//manifest")
            streams = hlsparse(self.options, self.http.request("get", elements[0].text), elements[0].text)
            for n in list(streams.keys()):
                yield streams[n]
