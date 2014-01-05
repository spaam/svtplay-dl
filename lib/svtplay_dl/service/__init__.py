# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import re
from svtplay_dl.utils.urllib import urlparse

class Service(object):
    supported_domains = []
    supported_domains_re = []

    def handles(self, url):
        urlp = urlparse(url)

        # Apply supported_domains_re regexp to the netloc. This
        # is meant for 'dynamic' domains, e.g. containing country
        # information etc.
        for domain_re in [re.compile(x) for x in self.supported_domains_re]:
            if domain_re.match(urlp.netloc):
                return True

        if urlp.netloc in self.supported_domains:
            return True

        # For every listed domain, try with www. subdomain as well.
        if urlp.netloc in ['www.'+x for x in self.supported_domains]:
            return True

        return False

from svtplay_dl.service.aftonbladet import Aftonbladet
from svtplay_dl.service.dr import Dr
from svtplay_dl.service.expressen import Expressen
from svtplay_dl.service.hbo import Hbo
from svtplay_dl.service.justin import Justin
from svtplay_dl.service.kanal5 import Kanal5
from svtplay_dl.service.mtvservices import Mtvservices
from svtplay_dl.service.nrk import Nrk
from svtplay_dl.service.qbrick import Qbrick
from svtplay_dl.service.ruv import Ruv
from svtplay_dl.service.radioplay import Radioplay
from svtplay_dl.service.sr import Sr
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.service.tv4play import Tv4play
from svtplay_dl.service.urplay import Urplay
from svtplay_dl.service.viaplay import Viaplay
from svtplay_dl.service.vimeo import Vimeo
from svtplay_dl.utils import get_http_data

sites = [
    Aftonbladet(),
    Dr(),
    Expressen(),
    Hbo(),
    Justin(),
    Kanal5(),
    Mtvservices(),
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


class Generic(object):
    ''' Videos embed in sites '''
    def get(self, url):
        data = get_http_data(url)
        match = re.search(r"src=\"(http://www.svt.se/wd.*)\" height", data)
        stream = None
        if match:
            url = match.group(1)
            for i in sites:
                if i.handles(url):
                    return url, i

        match = re.search(r"src=\"(http://player.vimeo.com/video/[0-9]+)\" ", data)
        if match:
            for i in sites:
                if i.handles(match.group(1)):
                    return match.group(1), i
        match = re.search(r"tv4video.swf\?vid=(\d+)", data)
        if match:
            url = "http://www.tv4play.se/?video_id=%s" % match.group(1)
            for i in sites:
                if i.handles(url):
                    return url, i
        return url, stream

def service_handler(url):
    handler = None

    for i in sites:
        if i.handles(url):
            handler = i
            break

    return handler
