#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import svtplay_dl.subtitle


class timestrTest(unittest.TestCase):
    # pylint seem to think that svtplay_dl.subtitle refers to a
    # class, not a module. Maybe it's confused, and got it mixed
    # up with svtplay_dl.subtitle.subtitle? The tests pass, so
    # i have the truth on my side.
    #   pylint: disable-msg=no-member

    def test_1(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(1), "00:00:00,00")

    def test_100(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(100), "00:00:00,10")

    def test_3600(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(3600), "00:00:03,60")

    def test_3600000(self):
        self.assertEqual(svtplay_dl.subtitle.timestr(3600000), "01:00:00,00")
