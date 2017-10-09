# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import unquote_plus
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Youplay(Service, OpenGraphThumbMixin):
    supported_domains = ['www.affarsvarlden.se']

    def get(self):
        data = self.get_urldata()

        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'script async defer src="(//content.youplay.se[^"]+)"', data)
        if not match:
            yield ServiceError("Cant find video info for {0}".format(self.url))
            return

        data = self.http.request("get", "http:{0}".format(match.group(1)).content)
        match = re.search(r'decodeURIComponent\("([^"]+)"\)\)', data)
        if not match:
            yield ServiceError("Can't decode video info")
            return
        data = unquote_plus(match.group(1))
        match = re.search(r"videoData = ({[^;]+});", data)
        if not match:
            yield ServiceError("Cant find video info for {0}".format(self.url))
            return
        # fix broken json.
        regex = re.compile(r"\s(\w+):")
        data = regex.sub(r"'\1':", match.group(1))
        data = data.replace("'", "\"")
        j = re.sub(r"{\s*(\w)", r'{"\1', data)
        j = j.replace("\n", "")
        j = re.sub(r'",\s*}', '"}', j)
        jsondata = json.loads(j)
        for i in jsondata["episode"]["sources"]:
            match = re.search(r"mp4_(\d+)", i)
            if match:
                yield HTTP(copy.copy(self.options), jsondata["episode"]["sources"][i], match.group(1))
