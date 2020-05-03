# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import copy
import json
import re

from svtplay_dl.error import ServiceError
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.service import Service


class Radioplay(Service):
    supported_domains = ["radioplay.se"]

    def get(self):
        data = self.get_urldata()

        match = re.search(r"RP.vcdData = ({.*});</script>", data)
        if match:
            data = json.loads(match.group(1))
            for i in list(data["station"]["streams"].keys()):
                yield HTTP(copy.copy(self.config), data["station"]["streams"][i], i)
        else:
            yield ServiceError("Can't find stream info")
            return
