#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import svtplay_dl.subtitle

class timestrTest(unittest.TestCase):
    def test_1(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(1), "00:00:00,00")

    def test_100(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(100), "00:00:00,10")

    def test_3600(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(3600), "00:00:03,60")

    def test_3600000(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(3600000), "01:00:00,00")
