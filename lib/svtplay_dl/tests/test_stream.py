import unittest

from svtplay_dl.fetcher.dash import DASH
from svtplay_dl.fetcher.hls import HLS
from svtplay_dl.fetcher.http import HTTP
from svtplay_dl.utils.parser import setup_defaults
from svtplay_dl.utils.stream import sort_quality


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
