from __future__ import absolute_import

import os
import unittest

from svtplay_dl.fetcher.dash import _dashparse
from svtplay_dl.fetcher.dash import parse_duration
from svtplay_dl.utils.parser import setup_defaults


def parse(playlist):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dash-manifests", playlist)) as fd:
        manifest = fd.read()

    return _dashparse(setup_defaults(), manifest, "http://localhost", None, None)


class dashtest(unittest.TestCase):
    def test_parse_cmore(self):
        data = parse("cmore.mpd")
        assert len(data[3261.367].files) == 410
        assert len(data[3261.367].audio) == 615
        assert data[3261.367].segments

    def test_parse_fff(self):
        data = parse("fff.mpd")
        assert len(data[3187.187].files) == 578
        assert len(data[3187.187].audio) == 577
        assert data[3187.187].segments

    def test_parse_nya(self):
        data = parse("svtvod.mpd")
        assert len(data[2793.0].files) == 350
        assert len(data[2793.0].audio) == 350
        assert data[2793.0].segments

    def test_parse_live(self):
        data = parse("svtplay-live.mpd")
        assert len(data[2795.9959999999996].files) == 6
        assert len(data[2795.9959999999996].audio) == 6
        assert data[2795.9959999999996].segments

    def test_parse_live2(self):
        data = parse("svtplay-live2.mpd")
        assert len(data[2892.0].files) == 11
        assert len(data[2892.0].audio) == 11
        assert data[2892.0].segments

    def test_parse_duration(self):
        assert parse_duration("PT3459.520S") == 3459.52
        assert parse_duration("PT2.00S") == 2.0
        assert parse_duration("PT1H0M30.000S") == 3630.0
        assert parse_duration("P1Y1M1DT1H0M30.000S") == 34218030.0
        assert parse_duration("PWroNG") == 0
