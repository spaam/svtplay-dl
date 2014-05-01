#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
from svtplay_dl.service.oppetarkiv import OppetArkiv

class handlesTest(unittest.TestCase):
    def handles_oppetarkiv_se_test(self):
        self.assertTrue(OppetArkiv.handles(
            "http://www.oppetarkiv.se/video/1129844/jacobs-stege-avsnitt-1-av-1"))

    def handles_svtplay_se_test(self):
        self.assertFalse(OppetArkiv.handles(
            "http://www.svtplay.se/video/1090393/del-9"))

