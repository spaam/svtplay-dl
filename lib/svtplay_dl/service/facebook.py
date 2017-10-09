from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import unquote_plus
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.error import ServiceError


class Facebook(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.facebook.com"]

    def get(self):
        data = self.get_urldata()

        match = re.search('params","([^"]+)"', data)
        if not match:
            yield ServiceError("Cant find params info. video need to be public.")
            return
        data2 = json.loads('["{0}"]'.format(match.group(1)))
        data2 = json.loads(unquote_plus(data2[0]))
        if "sd_src_no_ratelimit" in data2["video_data"]["progressive"][0]:
            yield HTTP(copy.copy(self.options), data2["video_data"]["progressive"][0]["sd_src_no_ratelimit"], "240")
        else:
            yield HTTP(copy.copy(self.options), data2["video_data"]["progressive"][0]["sd_src"], "240")
        if "hd_src_no_ratelimit" in data2["video_data"]["progressive"][0]:
            yield HTTP(copy.copy(self.options), data2["video_data"]["progressive"][0]["hd_src_no_ratelimit"], "720")
        else:
            if data2["video_data"]["progressive"][0]["hd_src"]:
                yield HTTP(copy.copy(self.options), data2["video_data"]["progressive"][0]["hd_src"], "720")
