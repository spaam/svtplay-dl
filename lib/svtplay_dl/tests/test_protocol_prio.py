#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8
import unittest

from svtplay_dl.utils.stream import protocol_prio


class VideoRetriever:
    def __init__(self, proto, bitrate):
        self.proto = proto
        self.bitrate = bitrate
        self.name = proto

    def __repr__(self):
        return "%s(%d)" % (self.proto.upper(), self.bitrate)


class PrioStreamsTest(unittest.TestCase):
    def _gen_proto_case(self, ordered, unordered, expected=None):
        streams = [VideoRetriever(x, 100) for x in unordered]

        kwargs = {}
        if expected is None:
            expected = [str(VideoRetriever(x, 100)) for x in ordered]

        return [str(x) for x in protocol_prio(streams, ordered, **kwargs)] == expected

    def test_custom_order(self):
        assert self._gen_proto_case(["http", "hds", "hls"], ["hds", "hls", "http"])

    def test_custom_order_1(self):
        assert self._gen_proto_case(["http"], ["hds", "hls", "http"])

    def test_proto_unavail(self):
        assert self._gen_proto_case(["http", "hds"], ["hls", "https"], expected=[])
