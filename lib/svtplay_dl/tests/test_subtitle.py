#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
from __future__ import absolute_import

import unittest
import xml.etree.ElementTree as ET

import svtplay_dl.subtitle


class timestrTest(unittest.TestCase):
    # pylint seem to think that svtplay_dl.subtitle refers to a
    # class, not a module. Maybe it's confused, and got it mixed
    # up with svtplay_dl.subtitle.subtitle? The tests pass, so
    # i have the truth on my side.
    #   pylint: disable-msg=no-member

    def test_1(self):
        assert svtplay_dl.subtitle.timestr(1) == "00:00:00,001"

    def test_100(self):
        assert svtplay_dl.subtitle.timestr(100) == "00:00:00,100"

    def test_3600(self):
        assert svtplay_dl.subtitle.timestr(3600) == "00:00:03,600"

    def test_3600000(self):
        assert svtplay_dl.subtitle.timestr(3600000) == "01:00:00,000"


class strdateTest(unittest.TestCase):
    def test_match(self):
        assert svtplay_dl.subtitle.strdate("21:33:30.33 --> 21:33:33.50")

    def test_notmatch(self):
        assert not svtplay_dl.subtitle.strdate("21:33:30.33 --> 21:33.33.50")


class sec2str(unittest.TestCase):
    def test_sec3600(self):
        assert svtplay_dl.subtitle.sec2str(3600) == "01:00:00.000"

    def test_sec3650(self):
        assert svtplay_dl.subtitle.sec2str(3650) == "01:00:50.000"

    def test_sec3002(self):
        assert svtplay_dl.subtitle.sec2str(3002.23) == "00:50:02.230"


class str2sec(unittest.TestCase):
    def test_str3600(self):
        assert svtplay_dl.subtitle.str2sec("01:01:01.000") == 3661.0

    def test_str3650(self):
        assert svtplay_dl.subtitle.str2sec("01:00:50.000") == 3650.0

    def test_str3002(self):
        assert svtplay_dl.subtitle.str2sec("00:50:02.230") == 3002.23


class timecolon(unittest.TestCase):
    def test_timecolon(self):
        assert svtplay_dl.subtitle.timecolon("00:50:02:230") == "00:50:02,230"


class normr(unittest.TestCase):
    def test_norm1(self):
        assert svtplay_dl.subtitle.norm("kalle") == "kalle"

    def test_norm2(self):
        assert svtplay_dl.subtitle.norm("{kalle}anka") == "anka"


class tt_text(unittest.TestCase):
    def test_tt_text1(self):
        assert svtplay_dl.subtitle.tt_text(ET.fromstring("<tests>kalle</tests>"), "") == "kalle\n"

    def test_tt_text2(self):
        assert svtplay_dl.subtitle.tt_text(ET.fromstring("<tests><test1>kalle</test1><test2>anka</test2></tests>"), "") == "kalle\nanka\n"

    def test_tt_text3(self):
        assert svtplay_dl.subtitle.tt_text(ET.fromstring("<tests><test1>hej</test1>kalle</tests>"), "") == "hej\nkalle\n"

    def test_tt_text4(self):
        assert svtplay_dl.subtitle.tt_text(ET.fromstring("<tests>kalle<test2>hej</test2></tests>"), "") == "kalle\nhej\n"

    def test_tt_text5(self):
        assert svtplay_dl.subtitle.tt_text(ET.fromstring("<tests><test>kalle</test>hej</tests>"), "") == "kalle\nhej\n"
