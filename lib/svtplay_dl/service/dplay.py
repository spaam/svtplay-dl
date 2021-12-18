# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from svtplay_dl.error import ServiceError
from svtplay_dl.service import Service


class Discoveryplus(Service):
    supported_domains = ["discoveryplus.se", "discoveryplus.no", "discoveryplus.dk", "discoveryplus.com"]

    def get(self):
        yield ServiceError("Can't download videos from this site anymore because of DRM")
