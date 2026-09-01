import unittest

from svtplay_dl.error import ServiceError
from svtplay_dl.service.svt import _page
from svtplay_dl.service.svt import _stream_data
from svtplay_dl.service.svt import Svt
from svtplay_dl.service.svtplay import timestamp
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

# A full article, everything _set_metadata reads.
FULL = [
    '[{\\"_1\\":2},\\"loaderData\\",{\\"_3\\":4},\\"layouts/RootLayout\\",{\\"_5\\":6},\\"page\\",{\\"_7\\":8,\\"_9\\":10,\\"_11\\":12,\\"_13\\":14,\\"_15\\":17},\\"__typename\\",\\"NewsArticle\\",\\"title\\",\\"Appar tar over barnens fritid\\",\\"published\\",\\"2026-08-28T05:30:05+02:00\\",\\"section\\",{\\"_29\\":16},\\"topMedia\\",\\"Gavleborg\\",{\\"_7\\":18,\\"_19\\":20,\\"_21\\":22,\\"_23\\":24,\\"_25\\":26},\\"Video\\",\\"svtId\\",\\"eZx7Y99\\",\\"metadataTitle\\",\\"Barnens kompisar ersatts av appar\\",\\"description\\",\\"Instagram, TikTok och Snapchat.\\",\\"poster\\",{\\"_27\\":28},\\"metaImage\\",\\"https://www.svtstatic.se/image-news/1280/16:9/x/y/z\\",\\"name\\"]',
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


class metadataTest(unittest.TestCase):
    def output(self, chunks):
        svt = Svt(setup_defaults(), URL)
        page = _page(_stream_data(page_data(chunks)))
        svt._set_metadata(page, page["topMedia"])
        return svt.output

    def test_full(self):
        output = self.output(FULL)
        assert output["title"] == "Gavleborg"
        assert output["title_nice"] == "Gavleborg"
        assert output["episodename"] == "Barnens kompisar ersatts av appar"
        assert output["id"] == "eZx7Y99"
        assert output["episodedescription"] == "Instagram, TikTok och Snapchat."
        assert output["episodethumbnailurl"] == "https://www.svtstatic.se/image-news/1280/16:9/x/y/z"
        assert output["publishing_datetime"] == timestamp("2026-08-28T05:30:05+02:00")
        assert output["tvshow"] is False

    def test_minimal(self):
        # No section, no poster, no description: fall back to the article title.
        output = self.output(ARTICLE)
        assert output["title"] is None
        assert output["episodename"] is None
        assert output["id"] == "eZx7Y99"
        assert output["episodethumbnailurl"] is None
        assert output["publishing_datetime"] is None
