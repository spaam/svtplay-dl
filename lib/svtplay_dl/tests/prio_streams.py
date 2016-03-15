#!/usr/bin/python
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil; coding: utf-8 -*-
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8

from __future__ import absolute_import
import unittest
from svtplay_dl.utils import prio_streams

class Stream(object):
    def __init__(self, proto, bitrate):
        self.proto = proto
        self.bitrate = bitrate
    def name(self):
        return self.proto
    def __repr__(self):
        return '%s(%d)' % (self.proto.upper(), self.bitrate)

class PrioStreamsTest(unittest.TestCase):
    def _gen_proto_case(self, ordered, unordered, default=True, expected=None):
        streams = [Stream(x, 100) for x in unordered]

        kwargs = {}
        if not default:
            kwargs['protocol_prio'] = ordered
        if expected is None:
            expected = [str(Stream(x, 100)) for x in ordered]

        return self.assertEqual(
            [str(x) for x in prio_streams(streams, **kwargs)],
            expected
        )

    def test_default_order(self):
        return self._gen_proto_case(
            ['hls', 'hds', 'http', 'rtmp'],
            ['rtmp', 'hds', 'hls', 'http']
        )

    def test_custom_order(self):
        return self._gen_proto_case(
            ['http', 'rtmp', 'hds', 'hls'],
            ['rtmp', 'hds', 'hls', 'http'],
            default=False,
        )

    def test_custom_order_1(self):
        return self._gen_proto_case(
            ['http'],
            ['rtmp', 'hds', 'hls', 'http'],
            default=False,
        )

    def test_proto_unavail(self):
        return self._gen_proto_case(
            ['http', 'rtmp'],
            ['hds', 'hls', 'https'],
            default=False,
            expected=[],
        )
