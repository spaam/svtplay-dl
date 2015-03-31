from __future__ import absolute_import
import re
import json
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.utils.urllib import unquote_plus
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.log import log


class Facebook(Service, OpenGraphThumbMixin):
    supported_domains_re = ["www.facebook.com"]

    def get(self, options):
        error, data = self.get_urldata()
        if error:
            log.error("Cant download page")
            return

        match = re.search('params","([^"]+)"', data)
        if not match:
            log.error("Cant find params info. video need to be public.")
            return
        data2 = json.loads('["%s"]' % match.group(1))
        data2 = json.loads(unquote_plus(data2[0]))
        if "sd_src_no_ratelimit" in data2["video_data"][0]:
            yield HTTP(copy.copy(options), data2["video_data"][0]["sd_src_no_ratelimit"], "240")
        else:
            yield HTTP(copy.copy(options), data2["video_data"][0]["sd_src"], "240")
        if "hd_src_no_ratelimit" in data2["video_data"][0]:
            yield HTTP(copy.copy(options), data2["video_data"][0]["hd_src_no_ratelimit"], "720")
        else:
            if data2["video_data"][0]["hd_src"]:
                yield HTTP(copy.copy(options), data2["video_data"][0]["hd_src"], "720")
