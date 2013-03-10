# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import

class Service(object):
    pass

class Generic(object):
    ''' Videos embed in sites '''
    def get(self, sites, url):
        data = get_http_data(url)
        match = re.search("src=\"(http://www.svt.se/wd.*)\" frameborder", data)
        stream = None
        if match:
            url = match.group(1)
            for i in sites:
                if i.handle(url):
                    return url, i

        match = re.search("src=\"(http://player.vimeo.com/video/[0-9]+)\" ", data)
        if match:
            for i in sites:
                if i.handle(match.group(1)):
                    return match.group(1), i
        return url, stream

from svtplay.service.aftonbladet import Aftonbladet
from svtplay.service.dr import Dr
from svtplay.service.expressen import Expressen
from svtplay.service.hbo import Hbo
from svtplay.service.justin import Justin
from svtplay.service.kanal5 import Kanal5
from svtplay.service.nrk import Nrk
from svtplay.service.qbrick import Qbrick
from svtplay.service.ruv import Ruv
from svtplay.service.radioplay import Radioplay
from svtplay.service.sr import Sr
from svtplay.service.svtplay import Svtplay
from svtplay.service.tv4play import Tv4play
from svtplay.service.urplay import Urplay
from svtplay.service.viaplay import Viaplay
from svtplay.service.vimeo import Vimeo


def service_handler(url):
    sites = [
        Aftonbladet(),
        Dr(),
        Expressen(),
        Hbo(),
        Justin(),
        Kanal5(),
        Nrk(),
        Qbrick(),
        Ruv(),
        Radioplay(),
        Sr(),
        Svtplay(),
        Tv4play(),
        Urplay(),
        Viaplay(),
        Vimeo()]

    handler = None

    for i in sites:
        if i.handle(url):
            handler = i
            break

    return handler
