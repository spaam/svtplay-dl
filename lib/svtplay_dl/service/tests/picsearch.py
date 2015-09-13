#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
from svtplay_dl.service.tests import HandlesURLsTestMixin
from svtplay_dl.service.picsearch import Picsearch

class handlesTest(unittest.TestCase, HandlesURLsTestMixin):
    service = Picsearch
    urls = {
        "ok": [
            "http://dn.se/valet-2014/sa-var-peter-wolodarskis-samtal-med-fredrik-reinfeldt/",
            "http://mobil.dn.se/valet-2014/sa-var-peter-wolodarskis-samtal-med-fredrik-reinfeldt/",
        ],
        "bad": [
            "http://www.oppetarkiv.se/video/1129844/jacobs-stege-ep1",
        ]
    }
