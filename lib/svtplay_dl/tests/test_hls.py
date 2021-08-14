#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
# We're a test, we go where ever we want (within reason, of course):
#   pylint: disable-msg=protected-access
import os
import unittest

import requests_mock
from svtplay_dl import fetcher
from svtplay_dl.fetcher.hls import _hlsparse
from svtplay_dl.fetcher.hls import M3U8
from svtplay_dl.utils.parser import setup_defaults


def parse(playlist):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "m3u8-playlists", playlist)) as fd:
        manifest = fd.read()
    streams = {}
    for i in list(_hlsparse(setup_defaults(), manifest, "http://localhost.com/", {})):
        if isinstance(i, fetcher.VideoRetriever):
            streams[i.bitrate] = i
    return streams


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

M3U_EXAMPLE2 = """#EXTM3U
#EXT-X-VERSION:4
## Created with Unified Streaming Platform(version=1.9.5)
#EXT-X-PLAYLIST-TYPE:VOD
#EXT-X-MEDIA-SEQUENCE:1
#EXT-X-INDEPENDENT-SEGMENTS
#EXT-X-TARGETDURATION:60
#USP-X-TIMESTAMP-MAP:MPEGTS=900000,LOCAL=1970-01-01T00:00:00Z
#EXTINF:60, no desc
pid200028961_3910568(3910568_ISMUSP)-textstream_swe=1000-1.webvtt
#EXTINF:60, no desc
pid200028961_3910568(3910568_ISMUSP)-textstream_swe=1000-2.webvtt
#EXTINF:60, no desc
pid200028961_3910568(3910568_ISMUSP)-textstream_swe=1000-3.webvtt
#EXTINF:60, no desc
pid200028961_3910568(3910568_ISMUSP)-textstream_swe=1000-4.webvtt
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


def test_noaudio_segment():
    with requests_mock.Mocker() as m:
        m.get("http://localhost.com/pid200028961_3910568(3910568_ISMUSP)-textstream_swe=1000.m3u8", text=M3U_EXAMPLE2)
        data = parse("no-audio-uri.m3u8")
        assert data[3642].segments is False
        assert data[3642].audio is None


def test_audio_top():
    with requests_mock.Mocker() as m:
        m.get("http://localhost.com/text/text-0.m3u8", text=M3U_EXAMPLE2)
        data = parse("audio-uri-top.m3u8")
        assert data[3295].segments
        assert data[3295].audio


def test_audio_bottom():
    data = parse("audio-uri-bottom.m3u8")
    assert data[2639].segments
    assert data[2639].audio
