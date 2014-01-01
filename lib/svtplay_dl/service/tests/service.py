#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import mock
from svtplay_dl.service import Service

class MockService(Service):
    supported_domains = ['example.com', 'example.net']

class ServiceTest(unittest.TestCase):
    def test_supports(self):
        service = MockService()
        self.assertTrue(service.handles('http://example.com/video.swf?id=1'))
        self.assertTrue(service.handles('http://example.net/video.swf?id=1'))
        self.assertTrue(service.handles('http://www.example.com/video.swf?id=1'))
        self.assertTrue(service.handles('http://www.example.net/video.swf?id=1'))
