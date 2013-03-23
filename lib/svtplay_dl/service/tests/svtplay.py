#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import svtplay.service.svtplay

class handleTest(unittest.TestCase):
    def setUp(self):
        self.svtplay = svtplay.service.svtplay.Svtplay()

    def handle_svtplay_se_test(self):
        self.assertTrue(self.svtplay.handle(
            "http://www.svtplay.se/video/1090393/del-9"))

    def handle_svt_se_test(self):
        self.assertTrue(self.svtplay.handle(
            "http://www.svt.se/nyheter/sverige/det-ar-en-dodsfalla"))

    def handle_dn_se_test(self):
        self.assertFalse(self.svtplay.handle(
            "http://www.dn.se/nyheter/sverige/det-ar-en-dodsfalla"))
