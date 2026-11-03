#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
import unittest

from svtplay_dl.service.tests import HandlesURLsTestMixin
from svtplay_dl.service.twitch import Twitch


class handlesTest(unittest.TestCase, HandlesURLsTestMixin):
    service = Twitch
    urls = {
        "ok": [
            "http://twitch.tv/foo/c/123456",
            "http://www.twitch.tv/foo/c/123456",
            "http://en.www.twitch.tv/foo/c/123456",
            "http://en.twitch.tv/foo/c/123456",
            "http://pt-br.twitch.tv/foo/c/123456",
            "http://pt-br.www.twitch.tv/foo/c/123456",
        ],
        "bad": [
            "http://www.dn.se/nyheter/sverige/det-ar-en-dodsfalla",
            "http://pxt-br.www.twitch.tv/foo/c/123456",
            "http://pxt-bxr.www.twitch.tv/foo/c/123456",
            "http://p-r.www.twitch.tv/foo/c/123456",
            "http://pxx.www.twitch.tv/foo/c/123456",
            "http://en.wwww.twitch.tv/foo/c/123456",
        ],
    }
