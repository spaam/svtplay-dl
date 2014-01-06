#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
from svtplay_dl.service.justin import Justin

class handlesTest(unittest.TestCase):

    def handles_true_test(self):
        self.assertTrue(Justin.handles(
            "http://twitch.tv/foo/c/123456"))
        self.assertTrue(Justin.handles(
            "http://www.twitch.tv/foo/c/123456"))
        self.assertTrue(Justin.handles(
            "http://en.www.twitch.tv/foo/c/123456"))
        self.assertTrue(Justin.handles(
            "http://en.twitch.tv/foo/c/123456"))
        self.assertTrue(Justin.handles(
            "http://pt-br.twitch.tv/foo/c/123456"))
        self.assertTrue(Justin.handles(
            "http://pt-br.www.twitch.tv/foo/c/123456"))

    def handles_false_test(self):
        self.assertFalse(Justin.handles(
            "http://www.dn.se/nyheter/sverige/det-ar-en-dodsfalla"))
        self.assertFalse(Justin.handles(
            "http://pxt-br.www.twitch.tv/foo/c/123456"))
        self.assertFalse(Justin.handles(
            "http://pxt-bxr.www.twitch.tv/foo/c/123456"))
        self.assertFalse(Justin.handles(
            "http://p-r.www.twitch.tv/foo/c/123456"))
        self.assertFalse(Justin.handles(
            "http://pxx.www.twitch.tv/foo/c/123456"))
        self.assertFalse(Justin.handles(
            "http://en.wwww.twitch.tv/foo/c/123456"))
