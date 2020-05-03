# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import OpenGraphThumbMixin
from svtplay_dl.service import Service


class Filmarkivet(Service, OpenGraphThumbMixin):
    supported_domains = ["filmarkivet.se"]

    def get(self):
        match = re.search(r'[^/]file: "(http[^"]+)', self.get_urldata())
        if not match:
            yield ServiceError("Can't find the video file")
            return
        yield HTTP(copy.copy(self.config), match.group(1), 480, output=self.output)
