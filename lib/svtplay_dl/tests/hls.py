#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

# We're a test, we go where ever we want (within reason, of course):
#   pylint: disable-msg=protected-access

from __future__ import absolute_import
import unittest
import svtplay_dl.fetcher.hls as hls
from svtplay_dl.fetcher.hls import M3U8
from svtplay_dl.utils import HTTP
from svtplay_dl import Options
import json


class HlsTest(unittest.TestCase):
    def test_get_full_url_1(self):
        for test in [
            # full http:// url as media segment in playlist
            {
                'srcurl': 'INVALID',
                'segment': 'http://example.com/',
                'expected': 'http://example.com/'
            },
            # full https:// url as media segment in playlist
            {
                'srcurl': 'INVALID',
                'segment': 'https://example.com/',
                'expected': 'https://example.com/'
            },
            # filename as media segment in playlist (http)
            {
                'srcurl': 'http://example.com/',
                'segment': 'foo.ts',
                'expected': 'http://example.com/foo.ts'
            },
            # filename as media segment in playlist (https)
            {
                'srcurl': 'https://example.com/',
                'segment': 'foo.ts',
                'expected': 'https://example.com/foo.ts'
            },
            # replacing srcurl file
            {
                'srcurl': 'http://example.com/bar',
                'segment': 'foo.ts',
                'expected': 'http://example.com/foo.ts'
            },
            # with query parameters
            {
                'srcurl': 'http://example.com/bar?baz=qux',
                'segment': 'foo.ts',
                'expected': 'http://example.com/foo.ts'
            },
        ]:
            self.assertEqual(
                hls._get_full_url(test['segment'], test['srcurl']),
                test['expected'])

    def test_parse_m3u8(self):
        for test in [
            # full http:// url as media segment in playlist
            {
                'srcurl': 'https://devstreaming-cdn.apple.com/videos/streaming/examples/bipbop_4x3/bipbop_4x3_variant.m3u8',
                'expected': '[{"PROGRAM-ID": "1", "BANDWIDTH": "232370", "TAG": "EXT-X-STREAM-INF", "URI": "gear1/prog_index.m3u8", "CODECS": "mp4a.40.2, avc1.4d4015"}, {"PROGRAM-ID": "1", "BANDWIDTH": "649879", "TAG": "EXT-X-STREAM-INF", "URI": "gear2/prog_index.m3u8", "CODECS": "mp4a.40.2, avc1.4d401e"}, {"PROGRAM-ID": "1", "BANDWIDTH": "991714", "TAG": "EXT-X-STREAM-INF", "URI": "gear3/prog_index.m3u8", "CODECS": "mp4a.40.2, avc1.4d401e"}, {"PROGRAM-ID": "1", "BANDWIDTH": "1927833", "TAG": "EXT-X-STREAM-INF", "URI": "gear4/prog_index.m3u8", "CODECS": "mp4a.40.2, avc1.4d401f"}, {"PROGRAM-ID": "1", "BANDWIDTH": "41457", "TAG": "EXT-X-STREAM-INF", "URI": "gear0/prog_index.m3u8", "CODECS": "mp4a.40.2"}]'
            }
            # More examples can be found on "https://developer.apple.com/streaming/examples/"
        ]:
            http = HTTP(Options())
            data = http.request("get", test['srcurl']).text
            self.assertEqual(
                json.dumps(M3U8(data).master_playlist),
                test['expected'])
