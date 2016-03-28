#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import svtplay_dl.fetcher.hls as hls


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
