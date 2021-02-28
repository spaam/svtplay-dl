import os
import unittest
from unittest.mock import patch

from requests import Response
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.postprocess import _checktracks
from svtplay_dl.postprocess import _getcodec
from svtplay_dl.postprocess import _streams
from svtplay_dl.postprocess import _sublanguage
from svtplay_dl.service import Service
from svtplay_dl.utils.parser import setup_defaults


class streams(unittest.TestCase):
    def test_audio1(self):
        audio = _streams("Stream #1:0: Audio: aac (LC), 48000 Hz, stereo, fltp, 126 kb/s")
        assert audio == [("1:0", "", "", "Audio", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s")]

    def test_audio2(self):
        audio = _streams("Stream #0:1(und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 125 kb/s (default)")
        assert audio == [("0:1", "(und)", "", "Audio", "aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 125 kb/s (default)")]

    def test_video1(self):
        video = _streams(
            "Stream #0:0[0x21]: Video: h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc",
        )
        assert video == [
            (
                "0:0",
                "[0x21]",
                "",
                "Video",
                "h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc",
            ),
        ]

    def test_video2(self):
        video = _streams(
            "Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1280x720 [SAR 1:1 DAR 16:9], 2710 kb/s, 25 fps, 25 tbr, 90k tbn, 50 tbc (default)",
        )
        assert video == [
            (
                "0:0",
                "(und)",
                "",
                "Video",
                "h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1280x720 [SAR 1:1 DAR 16:9], 2710 kb/s, 25 fps, 25 tbr, 90k tbn, 50 tbc (default)",
            ),
        ]

    def test_video3(self):
        video = _streams(
            "Stream #0:0: Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1280x720 [SAR 1:1 DAR 16:9], 2710 kb/s, 25 fps, 25 tbr, 90k tbn, 50 tbc (default)",
        )
        assert video == [
            (
                "0:0",
                "",
                "",
                "Video",
                "h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709), 1280x720 [SAR 1:1 DAR 16:9], 2710 kb/s, 25 fps, 25 tbr, 90k tbn, 50 tbc (default)",
            ),
        ]


class getcodec(unittest.TestCase):
    def test_codec1(self):
        assert (
            _getcodec([("1:0", "", "", "Audio", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s")], "1:0") == "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s"
        )

    def test_codec2(self):
        assert (
            _getcodec(
                [
                    (
                        "0:0",
                        "[0x21]",
                        "",
                        "Video",
                        "h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc",
                    ),
                ],
                "0:0",
            )
            == "h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc"
        )

    def test_codec3(self):
        assert not (_getcodec([("1:0", "", "", "Audio", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s")], "0:0"))


class checktracks(unittest.TestCase):
    def test_cktracks1(self):
        assert (
            _checktracks(
                [
                    ("1:0", "", "", "Audio", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s"),
                    (
                        "0:0",
                        "[0x21]",
                        "",
                        "Video",
                        "h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc",
                    ),
                ],
            )
            == ("0:0", "1:0")
        )

    def test_cktracks2(self):
        assert (
            _checktracks(
                [
                    ("1:0", "", "", "Substr", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s"),
                    (
                        "0:0",
                        "[0x21]",
                        "",
                        "Video",
                        "h264 (High) ([27][0][0][0] / 0x001B), yuv420p(progressive), 1920x1080 [SAR 1:1 DAR 16:9], 25 fps, 25 tbr, 90k tbn, 50 tbc",
                    ),
                ],
            )
            == ("0:0", None)
        )

    def test_cktracks3(self):
        assert _checktracks([("1:0", "", "", "Audio", "aac (LC), 48000 Hz, stereo, fltp, 126 kb/s")]) == (None, "1:0")

    def test_cktracks4(self):
        assert _checktracks([("1:0", "", "", "Audio", "mp3, 0 channels")]) == (None, None)


@patch("svtplay_dl.postprocess.post")
class sublang(unittest.TestCase):
    def setup_mock(self, req, lang):
        class MockResponse(Response):
            def __init__(self, lang, status=200):
                self.status_code = status
                self._json = {"language": lang}

            def json(self):
                return self._json

        req.return_value = MockResponse(lang)

    def test_sublang(self, req):
        config = setup_defaults()
        self.setup_mock(req, "swe")
        config.set("output", os.path.join(os.path.dirname(os.path.realpath(__file__)), "postprocess/textfile-service"))
        service = Service(config, "http://exmaple.com")
        service.output["title"] = "textfile"
        stream = VideoRetriever(config, "http://example.com", 0, output=service.output)
        self.assertEqual(_sublanguage(stream, config, None), ["swe"])

    def test_sublang2(self, req):
        config = setup_defaults()
        self.setup_mock(req, "swe")
        config.set("output", os.path.join(os.path.dirname(os.path.realpath(__file__)), "postprocess/textfile-service"))
        config.set("get_all_subtitles", True)
        service = Service(config, "http://exmaple.com")
        service.output["title"] = "textfile"
        stream = VideoRetriever(config, "http://example.com", 0, output=service.output)
        self.assertEqual(_sublanguage(stream, config, ["grej", "hej"]), ["swe", "swe"])

    def test_sublang3(self, req):
        config = setup_defaults()
        self.setup_mock(req, "smj")
        config.set("output", os.path.join(os.path.dirname(os.path.realpath(__file__)), "postprocess/textfile-service"))
        config.set("get_all_subtitles", True)
        service = Service(config, "http://exmaple.com")
        service.output["title"] = "textfile"
        stream = VideoRetriever(config, "http://example.com", 0, output=service.output)
        self.assertEqual(_sublanguage(stream, config, ["lulesamiska"]), ["smj"])
