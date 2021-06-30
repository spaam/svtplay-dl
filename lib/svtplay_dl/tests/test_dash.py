import datetime
import os

import pytest
from svtplay_dl.fetcher.dash import _dashparse
from svtplay_dl.fetcher.dash import parse_dates
from svtplay_dl.fetcher.dash import parse_duration
from svtplay_dl.utils.parser import setup_defaults


def parse(playlist):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dash-manifests", playlist)) as fd:
        manifest = fd.read()
    streams = {}
    for i in list(_dashparse(setup_defaults(), manifest, "http://localhost", {}, None)):
        streams[i.bitrate] = i
    return streams


def test_parse_cmore():
    data = parse("cmore.mpd")
    assert len(data[3261].files) == 410
    assert len(data[3261].audio) == 615
    assert data[3261].segments


def test_parse_fff():
    data = parse("fff.mpd")
    assert len(data[3187].files) == 578
    assert len(data[3187].audio) == 577
    assert data[3187].segments


def test_parse_nya():
    data = parse("svtvod.mpd")
    assert len(data[2793].files) == 350
    assert len(data[2793].audio) == 350
    assert data[2793].segments


def test_parse_live():
    data = parse("svtplay-live.mpd")
    assert len(data[2795].files) == 6
    assert len(data[2795].audio) == 6
    assert data[2795].segments


def test_parse_live2():
    data = parse("svtplay-live2.mpd")
    assert len(data[2892.0].files) == 11
    assert len(data[2892.0].audio) == 11
    assert data[2892.0].segments


def test_parse_live_vod():
    data = parse("direct-live.mpd")
    assert len(data[4720.0].files) == 4424
    assert len(data[4720.0].audio) == 4424
    assert data[4720.0].segments


def test_parse_duration():
    assert parse_duration("PT3459.520S") == 3459.52
    assert parse_duration("PT2.00S") == 2.0
    assert parse_duration("PT1H0M30.000S") == 3630.0
    assert parse_duration("P1Y1M1DT1H0M30.000S") == 34218030.0
    assert parse_duration("mMWroNG") == 0


def test_parse_date():
    assert isinstance(parse_dates("2021-05-10T06:00:11.451554796Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.45155479Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.4515547Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.451554Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.45155Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.4515Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11.45Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11Z"), datetime.datetime)
    assert isinstance(parse_dates("2021-05-10T06:00:11"), datetime.datetime)
    with pytest.raises(ValueError):
        assert parse_dates("2021-05-10Z06:00:11.45Z")
