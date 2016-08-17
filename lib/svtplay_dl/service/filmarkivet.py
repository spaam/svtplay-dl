# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
import copy

from svtplay_dl.service import Service, OpenGraphThumbMixin
from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP


class Filmarkivet(Service, OpenGraphThumbMixin):
    supported_domains = ["filmarkivet.se"]

    def get(self):
        if self.exclude():
            yield ServiceError("Excluding video")
            return

        match = re.search(r'[^/]file: "(http[^"]+)', self.get_urldata())
        if not match:
            yield ServiceError("Can't find the video file")
            return
        yield HTTP(copy.copy(self.options), match.group(1), 480)