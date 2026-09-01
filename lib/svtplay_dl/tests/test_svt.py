import unittest

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svt import _all_videos
from svtplay_dl.service.svt import _page
from svtplay_dl.service.svt import _stream_data
from svtplay_dl.service.svt import Svt
from svtplay_dl.utils.parser import setup_defaults

URL = "https://www.svt.se/nyheter/lokalt/gavleborg/appar-tar-over-barnens-fritid"

# The payload svt.se embeds, split over two enqueue calls like the real pages do.
ARTICLE = [
    '[{\\"_1\\":2},\\"loaderData\\",{\\"_3\\":4},\\"layouts/RootLayout\\",{\\"_5\\":6},\\"page\\",{\\"_7\\":8,\\"_9\\":10',
    '},\\"__typename\\",\\"NewsArticle\\",\\"topMedia\\",{\\"_7\\":11,\\"_12\\":13},\\"Video\\",\\"svtId\\",\\"eZx7Y99\\"]',
]
NO_VIDEO = [
    '[{\\"_1\\":2},\\"loaderData\\",{\\"_3\\":4},\\"layouts/RootLayout\\",{\\"_5\\":6},\\"page\\",{\\"_7\\":8},\\"__typename\\",\\"NewsArticle\\"]',
]
# Points back at itself, so unflattening it must not recurse forever.
CYCLIC = ['[{\\"_1\\":2},\\"loaderData\\",{\\"_1\\":2}]']

# topMedia plus a clip in the body and one on a live report post.
MANY = [
    '[{\\"_1\\":2},\\"loaderData\\",{\\"_3\\":4},\\"layouts/RootLayout\\",{\\"_5\\":6},\\"page\\",{\\"_7\\":8,\\"_9\\":10,\\"_12\\":13,\\"_17\\":18},\\"__typename\\",\\"BreakingArticle\\",\\"topMedia\\",{\\"_11\\":22},\\"svtId\\",\\"body\\",[14],{\\"_15\\":16},\\"video\\",{\\"_11\\":23},\\"liveStream\\",{\\"_19\\":20},\\"posts\\",[21],{\\"_24\\":25},\\"eZx7Y99\\",\\"KxgaW2Z\\",\\"attachment\\",{\\"_11\\":26},\\"jR5GJ4y\\"]',
]


def page_data(chunks):
    enqueue = "".join(f'window.__reactRouterContext.streamController.enqueue("{chunk}");' for chunk in chunks)
    return f"<html><body><script>{enqueue}window.__reactRouterContext.streamController.close();</script></body></html>"


class streamDataTest(unittest.TestCase):
    def test_chunks(self):
        page = _page(_stream_data(page_data(ARTICLE)))
        assert page["__typename"] == "NewsArticle"
        assert page["topMedia"]["svtId"] == "eZx7Y99"

    def test_no_video(self):
        assert _page(_stream_data(page_data(NO_VIDEO))) == {"__typename": "NewsArticle"}

    def test_cyclic(self):
        janson = _stream_data(page_data(CYCLIC))
        assert janson["loaderData"]["loaderData"] is janson["loaderData"]

    def test_no_payload(self):
        assert _stream_data("<html><body>nothing here</body></html>") is None
        assert _page(None) is None


class svtTest(unittest.TestCase):
    def service(self, data):
        svt = Svt(setup_defaults(), URL)
        svt._urldata = data
        return svt

    def test_no_payload(self):
        error = list(self.service("<html></html>").get())
        assert isinstance(error[0], ServiceError)
        assert str(error[0]) == "Can't find video info."

    def test_no_video(self):
        error = list(self.service(page_data(NO_VIDEO)).get())
        assert isinstance(error[0], ServiceError)
        assert str(error[0]) == "Can't find any videos"


class allVideosTest(unittest.TestCase):
    def videos(self, chunks):
        return _all_videos(_page(_stream_data(page_data(chunks))))

    def test_many(self):
        # The main video first, then the rest in the order the page has them.
        assert self.videos(MANY) == ["eZx7Y99", "KxgaW2Z", "jR5GJ4y"]

    def test_one(self):
        assert self.videos(ARTICLE) == ["eZx7Y99"]

    def test_none(self):
        assert self.videos(NO_VIDEO) == []

    def test_episodes(self):
        svt = Svt(setup_defaults(), URL)
        svt._urldata = page_data(MANY)
        assert svt.find_all_episodes(svt.config) == [
            "https://www.svtplay.se/video/jR5GJ4y",
            "https://www.svtplay.se/video/KxgaW2Z",
            "https://www.svtplay.se/video/eZx7Y99",
        ]

    def test_episodes_no_payload(self):
        svt = Svt(setup_defaults(), URL)
        svt._urldata = "<html></html>"
        assert svt.find_all_episodes(svt.config) == []

    def test_cyclic(self):
        # _stream_data can hand back a structure that points at itself.
        page = {"topMedia": {"svtId": "eZx7Y99"}}
        page["self"] = page
        assert _all_videos(page) == ["eZx7Y99"]
