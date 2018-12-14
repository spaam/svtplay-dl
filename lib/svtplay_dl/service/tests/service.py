#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
from svtplay_dl.service import Service, service_handler, opengraph_get
from svtplay_dl.service.services import sites
from svtplay_dl.utils.parser import setup_defaults


class MockService(Service):
    supported_domains = ['example.com', 'example.net']


class ServiceTest(unittest.TestCase):
    def test_supports(self):
        self.assertTrue(MockService.handles('http://example.com/video.swf?id=1'))
        self.assertTrue(MockService.handles('http://example.net/video.swf?id=1'))
        self.assertTrue(MockService.handles('http://www.example.com/video.swf?id=1'))
        self.assertTrue(MockService.handles('http://www.example.net/video.swf?id=1'))


class service_handlerTest(unittest.TestCase):
    def test_service_handler(self):
        config = setup_defaults()
        self.assertIsNone(service_handler(sites, config, "localhost"))


class service_handlerTest2(unittest.TestCase):
    def test_service_handler(self):
        config = setup_defaults()
        self.assertIsInstance(service_handler(sites, config, "https://www.svtplay.se"), Service)


class service_opengraphGet(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg"><meta'

    def test_og_get(self):
        self.assertEqual(opengraph_get(self.text, "image"), "http://example.com/img3.jpg")


class service_opengraphGet_none(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg"><meta'

    def test_og_get(self):
        self.assertIsNone(opengraph_get(self.text, "kalle"))


class service_opengraphGet2(unittest.TestCase):
    text = '<html><head><meta name="og:image" property="og:image" content="http://example.com/img3.jpg">'

    def test_og_get(self):
        self.assertEqual(opengraph_get(self.text, "image"), "http://example.com/img3.jpg")
