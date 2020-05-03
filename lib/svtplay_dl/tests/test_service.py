import unittest

from svtplay_dl.service import Generic
from svtplay_dl.service import opengraph_get
from svtplay_dl.service import Service
from svtplay_dl.service import service_handler
from svtplay_dl.service.services import sites
from svtplay_dl.utils.parser import setup_defaults


class MockService(Service):
    supported_domains = ["example.com", "example.net"]


class ServiceTest(unittest.TestCase):
    def test_supports(self):
        assert MockService.handles("http://example.com/video.swf?id=1")
        assert MockService.handles("http://example.net/video.swf?id=1")
        assert MockService.handles("http://www.example.com/video.swf?id=1")
        assert MockService.handles("http://www.example.net/video.swf?id=1")


class service_handlerTest(unittest.TestCase):
    def test_service_handler(self):
        config = setup_defaults()
        assert not service_handler(sites, config, "localhost")


class service_handlerTest2(unittest.TestCase):
    def test_service_handler(self):
        config = setup_defaults()
        assert isinstance(service_handler(sites, config, "https://www.svtplay.se"), Service)


class service_opengraphGet(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg"><meta'

    def test_og_get(self):
        assert opengraph_get(self.text, "image") == "http://example.com/img3.jpg"


class service_opengraphGet_none(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg"><meta'

    def test_og_get(self):
        assert not opengraph_get(self.text, "kalle")


class service_opengraphGet2(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg">'

    def test_og_get(self):
        assert opengraph_get(self.text, "image") == "http://example.com/img3.jpg"


class test_generic(unittest.TestCase):
    def test_nothing(self):
        config = setup_defaults()
        generic = Generic(config, "http://example.com")
        data = "hejsan"
        assert generic._match(data, sites) == ("http://example.com", None)

    def test_hls(self):
        config = setup_defaults()
        generic = Generic(config, "http://example.com")
        data = 'source src="http://example.com/hls.m3u8" type="application/x-mpegURL"'
        assert isinstance(generic._match(data, sites)[1], Service)

    def test_tv4(self):
        config = setup_defaults()
        generic = Generic(config, "http://example.com")
        data = "rc=https://www.tv4play.se/iframe/video/12499319 "
        assert isinstance(generic._match(data, sites)[1], Service)

    def test_vimeo(self):
        config = setup_defaults()
        generic = Generic(config, "http://example.com")
        data = 'src="https://player.vimeo.com/video/359281775" '
        assert isinstance(generic._match(data, sites)[1], Service)
