#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
# We're a test, we go where ever we want (within reason, of course):
#   pylint: disable-msg=protected-access
import unittest

from svtplay_dl.fetcher.hls import M3U8

# Example HLS playlist, source:
# loosly inspired by
# https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_4x3/bipbop_4x3_variant.m3u8
M3U_EXAMPLE = """#EXTM3U


#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=232370,CODECS="mp4a.40.2, avc1.4d4015"
something1/else.m3u8

#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=649879,CODECS="mp4a.40.2, avc1.4d401e"
something2/else.m3u8

#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=991714,CODECS="mp4a.40.2, avc1.4d401e"
something3/else.m3u8

#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1927833,CODECS="mp4a.40.2, avc1.4d401f"
something4/else.m3u8

#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=41457,CODECS="mp4a.40.2"
something0/else.m3u8
"""


class HlsTest(unittest.TestCase):
    def test_parse_m3u8(self):
        self.maxDiff = None
        for test in [
            # full http:// url as media segment in playlist
            {
                "playlist": M3U_EXAMPLE,
                "expected": [
                    {
                        "PROGRAM-ID": "1",
                        "BANDWIDTH": "232370",
                        "TAG": "EXT-X-STREAM-INF",
                        "URI": "something1/else.m3u8",
                        "CODECS": "mp4a.40.2, avc1.4d4015",
                    },
                    {
                        "PROGRAM-ID": "1",
                        "BANDWIDTH": "649879",
                        "TAG": "EXT-X-STREAM-INF",
                        "URI": "something2/else.m3u8",
                        "CODECS": "mp4a.40.2, avc1.4d401e",
                    },
                    {
                        "PROGRAM-ID": "1",
                        "BANDWIDTH": "991714",
                        "TAG": "EXT-X-STREAM-INF",
                        "URI": "something3/else.m3u8",
                        "CODECS": "mp4a.40.2, avc1.4d401e",
                    },
                    {
                        "PROGRAM-ID": "1",
                        "BANDWIDTH": "1927833",
                        "TAG": "EXT-X-STREAM-INF",
                        "URI": "something4/else.m3u8",
                        "CODECS": "mp4a.40.2, avc1.4d401f",
                    },
                    {"PROGRAM-ID": "1", "BANDWIDTH": "41457", "TAG": "EXT-X-STREAM-INF", "URI": "something0/else.m3u8", "CODECS": "mp4a.40.2"},
                ],
            },
            # More examples can be found on "https://developer.apple.com/streaming/examples/"
        ]:
            assert M3U8(test["playlist"]).master_playlist == test["expected"]
