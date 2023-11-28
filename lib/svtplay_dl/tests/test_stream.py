import unittest

from svtplay_dl.fetcher.dash import DASH
from svtplay_dl.fetcher.hls import HLS
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.parser import setup_defaults
from svtplay_dl.utils.stream import audio_role
from svtplay_dl.utils.stream import format_prio
from svtplay_dl.utils.stream import language_prio
from svtplay_dl.utils.stream import sort_quality
from svtplay_dl.utils.stream import subtitle_filter


class streamTest_sort(unittest.TestCase):
    def test_sort(self):
        data = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            HLS(setup_defaults(), "http://example.com", 2000, None),
            HTTP(setup_defaults(), "http://example.com", 3001, None),
        ]
        assert all(
            [
                a[0] == b.bitrate
                for a, b in zip(
                    sort_quality(data),
                    [
                        HTTP(setup_defaults(), "http://example.com", 3001, None),
                        DASH(setup_defaults(), "http://example.com", 3000, None),
                        HLS(setup_defaults(), "http://example.com", 2000, None),
                    ],
                )
            ],
        )


class streamTestLanguage(unittest.TestCase):
    def test_language_prio(self):
        config = setup_defaults()
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        streams = language_prio(config, test_streams)
        assert len(streams) == 3

    def test_language_prio_select(self):
        config = setup_defaults()
        config.set("audio_language", "en")
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None, language="en"),
            DASH(setup_defaults(), "http://example.com", 3001, None),
            DASH(setup_defaults(), "http://example.com", 3002, None, language="sv"),
        ]
        streams = language_prio(config, test_streams)
        assert len(streams) == 1


class streamTestFormat(unittest.TestCase):
    def test_language_prio(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, channels="51"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        streams = format_prio(test_streams, ["h264-51"])
        assert len(streams) == 1

    def test_language_prio2(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, channels="51"),
            DASH(setup_defaults(), "http://example.com", 3001, None, codec="h264", channels="51"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        streams = format_prio(test_streams, ["h264"])
        assert len(streams) == 2

    def test_language_prio3(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, channels="51"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        streams = format_prio(test_streams, ["h26e4"])
        assert len(streams) == 0


class streamTestRole(unittest.TestCase):
    def test_language_prio(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        streams = audio_role(setup_defaults(), test_streams)
        assert len(streams) == 3

    def test_language_prio2(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, role="x-sv"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        config = setup_defaults()
        config.set("audio_role", "x-sv")
        streams = audio_role(config, test_streams)
        assert len(streams) == 1

    def test_language_prio3(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, role="x-sv"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        config = setup_defaults()
        config.set("audio_role", "sv")
        streams = audio_role(config, test_streams)
        assert len(streams) == 0

    def test_language_prio4(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, role="x-sv"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        config = setup_defaults()
        config.set("audio_language", "sv")
        streams = audio_role(config, test_streams)
        assert len(streams) == 3

    def test_language_prio5(self):
        test_streams = [
            DASH(setup_defaults(), "http://example.com", 3000, None),
            DASH(setup_defaults(), "http://example.com", 3001, None, role="x-sv"),
            DASH(setup_defaults(), "http://example.com", 3002, None),
        ]
        config = setup_defaults()
        config.set("audio_role", "isii")
        config.set("audio_language", "sv")
        streams = audio_role(config, test_streams)
        assert len(streams) == 0


class streamSubtile(unittest.TestCase):
    def test_subtitleFilter(self):
        test_subs = [
            subtitle(setup_defaults(), "wrst", "http://example.com"),
            subtitle(setup_defaults(), "wrst", "http://example.com", subfix="sv"),
            subtitle(setup_defaults(), "wrst", "http://example.com", subfix="dk"),
            subtitle(setup_defaults(), "wrst", "http://example.com", subfix="sv"),
        ]
        subs = subtitle_filter(test_subs)
        assert len(subs) == 3

    def test_subtitleFilter2(self):
        config = setup_defaults()
        config.set("get_all_subtitles", True)
        test_subs = [
            subtitle(config, "wrst", "http://example.com"),
            subtitle(config, "wrst", "http://example.com", subfix="sv"),
            subtitle(config, "wrst", "http://example.com", subfix="dk"),
            subtitle(config, "wrst", "http://example.com", subfix="no"),
        ]
        subs = subtitle_filter(test_subs)
        assert len(subs) == 3

    def test_subtitleFilter3(self):
        config = setup_defaults()
        config.set("subtitle_preferred", "sv")
        test_subs = [
            subtitle(config, "wrst", "http://example.com"),
            subtitle(config, "wrst", "http://example.com", subfix="sv"),
            subtitle(config, "wrst", "http://example.com", subfix="dk"),
            subtitle(config, "wrst", "http://example.com", subfix="no"),
        ]
        subs = subtitle_filter(test_subs)
        assert len(subs) == 1

    def test_subtitleFilter4(self):
        config = setup_defaults()
        config.set("subtitle_preferred", "gr")
        test_subs = [
            subtitle(config, "wrst", "http://example.com"),
            subtitle(config, "wrst", "http://example.com", subfix="sv"),
            subtitle(config, "wrst", "http://example.com", subfix="dk"),
            subtitle(config, "wrst", "http://example.com", subfix="no"),
        ]
        subs = subtitle_filter(test_subs)
        assert len(subs) == 0

    def test_subtitleFilter5(self):
        config = setup_defaults()
        config.set("get_all_subtitles", True)
        test_subs = [
            subtitle(config, "wrst", "http://example.com"),
            subtitle(config, "wrst", "http://example.com", subfix="sv"),
            subtitle(config, "wrst", "http://example.com", subfix="sv"),
            subtitle(config, "wrst", "http://example.com", subfix="no"),
        ]
        subs = subtitle_filter(test_subs)
        assert len(subs) == 2
