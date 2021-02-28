# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import logging
import os
import re
from urllib.parse import urlparse

from svtplay_dl.utils.http import download_thumbnails
from svtplay_dl.utils.http import HTTP
from svtplay_dl.utils.parser import merge
from svtplay_dl.utils.parser import readconfig
from svtplay_dl.utils.parser import setup_defaults


class Service:
    supported_domains = []
    supported_domains_re = []

    def __init__(self, config, _url, http=None):
        self._url = _url
        self._urldata = None
        self._error = False
        self.subtitle = None
        self.cookies = {}
        self.auto_name = None
        self.output = {
            "title": None,
            "season": None,
            "episode": None,
            "episodename": None,
            "id": None,
            "service": self.__class__.__name__.lower(),
            "tvshow": None,
            "title_nice": None,
            "showdescription": None,
            "episodedescription": None,
            "showthumbnailurl": None,
            "episodethumbnailurl": None,
            "publishing_datetime": None,
        }

        #  Config
        if config.get("configfile") and os.path.isfile(config.get("configfile")):
            self.config = merge(
                readconfig(setup_defaults(), config.get("configfile"), service=self.__class__.__name__.lower()).get_variable(),
                config.get_variable(),
            )
        else:
            self.config = config

        if not http:
            self.http = HTTP(self.config)
        else:
            self.http = http

        logging.debug(f"service: {self.__class__.__name__.lower()}")

    @property
    def url(self):
        return self._url

    def get_urldata(self):
        if self._urldata is None:
            self._urldata = self.http.request("get", self.url).text
        return self._urldata

    @classmethod
    def handles(cls, url):
        urlp = urlparse(url)

        # Apply supported_domains_re regexp to the netloc. This
        # is meant for 'dynamic' domains, e.g. containing country
        # information etc.
        for domain_re in [re.compile(x) for x in cls.supported_domains_re]:
            if domain_re.match(urlp.netloc):
                return True

        if urlp.netloc in cls.supported_domains:
            return True

        # For every listed domain, try with www.subdomain as well.
        if urlp.netloc in ["www." + x for x in cls.supported_domains]:
            return True

        return False

    def get_subtitle(self, options):
        pass

    # the options parameter is unused, but is part of the
    # interface, so we don't want to remove it. Thus, the
    # pylint ignore.
    def find_all_episodes(self, options):  # pylint: disable-msg=unused-argument
        logging.warning("--all-episodes not implemented for this service")
        return [self.url]


def opengraph_get(html, prop):
    """
    Extract specified OpenGraph property from html.

        >>> opengraph_get('<html><head><meta property="og:image" content="http://example.com/img.jpg"><meta ...', "image")
        'http://example.com/img.jpg'
        >>> opengraph_get('<html><head><meta content="http://example.com/img2.jpg" property="og:image"><meta ...', "image")
        'http://example.com/img2.jpg'
        >>> opengraph_get('<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg"><meta ...', "image")
        'http://example.com/img3.jpg'
    """
    match = re.search('<meta [^>]*property="og:' + prop + '" content="([^"]*)"', html)
    if match is None:
        match = re.search('<meta [^>]*content="([^"]*)" property="og:' + prop + '"', html)
        if match is None:
            return None
    return match.group(1)


class OpenGraphThumbMixin:
    """
    Mix this into the service class to grab thumbnail from OpenGraph properties.
    """

    def get_thumbnail(self, options):
        url = opengraph_get(self.get_urldata(), "image")
        if url is None:
            return
        download_thumbnails(self.output, options, [(False, url)])


class MetadataThumbMixin:
    """
    Mix this into the service class to grab thumbnail from extracted metadata.
    """

    def get_thumbnail(self, options):
        urls = []
        if self.output["showthumbnailurl"] is not None:
            urls.append((True, self.output["showthumbnailurl"]))
        if self.output["episodethumbnailurl"] is not None:
            urls.append((False, self.output["episodethumbnailurl"]))
        if urls:
            download_thumbnails(self.output, options, urls)


class Generic(Service):
    """ Videos embed in sites """

    def get(self, sites):
        data = self.http.request("get", self.url).text
        return self._match(data, sites)

    def _match(self, data, sites):
        match = re.search(r"src=(\"|\')(http://www.svt.se/wd[^\'\"]+)(\"|\')", data)
        stream = None
        if match:
            url = match.group(2)
            for i in sites:
                if i.handles(url):
                    url = url.replace("&amp;", "&").replace("&#038;", "&")
                    return url, i(self.config, url)

        matchlist = [
            r"src=\"(https://player.vimeo.com/video/[0-9]+)\" ",
            r'src="(http://tv.aftonbladet[^"]*)"',
            r'a href="(http://tv.aftonbladet[^"]*)" class="abVi',
            r"iframe src='(http://www.svtplay[^']*)'",
            'src="(http://mm-resource-service.herokuapp.com[^"]*)"',
            r'src="([^.]+\.solidtango.com[^"+]+)"',
            's.src="(https://csp-ssl.picsearch.com[^"]+|http://csp.picsearch.com/rest[^"]+)',
        ]
        for i in matchlist:
            match = re.search(i, data)
            if match:
                url = match.group(1)
                for n in sites:
                    if n.handles(match.group(1)):
                        return match.group(1), n(self.config, url)

        match = re.search(r"tv4play.se/iframe/video/(\d+)?", data)
        if match:
            url = "http://www.tv4play.se/?video_id=%s" % match.group(1)
            for i in sites:
                if i.handles(url):
                    return url, i(self.config, url)

        match = re.search("(lemonwhale|lwcdn.com)", data)
        if match:
            url = "http://lemonwhale.com"
            for i in sites:
                if i.handles(url):
                    return self.url, i(self.config, self.url)

        match = re.search("(picsearch_ajax_auth|screen9-ajax-auth)", data)
        if match:
            url = "http://csp.picsearch.com"
            for i in sites:
                if i.handles(url):
                    return self.url, i(self.config, self.url)

        match = re.search('iframe src="(//csp.screen9.com[^"]+)"', data)
        if match:
            url = "http:%s" % match.group(1)
            for i in sites:
                if i.handles(url):
                    return self.url, i(self.config, self.url)

        match = re.search('source src="([^"]+)" type="application/x-mpegURL"', data)
        if match:
            for i in sites:
                if i.__name__ == "Raw":
                    return self.url, i(self.config, match.group(1))

        return self.url, stream


def service_handler(sites, options, url):
    handler = None

    for i in sites:
        if i.handles(url):
            handler = i(options, url)
            break

    return handler
