#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
import unittest

from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.service.tests import HandlesURLsTestMixin


class handlesTest(unittest.TestCase, HandlesURLsTestMixin):
    service = Svtplay
    urls = {
        "ok": ["http://www.svtplay.se/video/1090393/del-9", "http://www.svt.se/nyheter/sverige/det-ar-en-dodsfalla"],
        "bad": ["http://www.oppetarkiv.se/video/1129844/jacobs-stege-ep1", "http://www.dn.se/nyheter/sverige/det-ar-en-dodsfalla"],
    }
