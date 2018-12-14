#!/usr/bin/python
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil; coding: utf-8 -*-
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
from svtplay_dl.utils.text import filenamify


class filenamifyTest(unittest.TestCase):
    test_values = [
        ["foo", "foo"],
        ["foo bar", "foo.bar"],
        ["FOO BAR", "foo.bar"],
        ['foo-bar baz', "foo-bar.baz"],
        [u'Jason "Timbuktu" Diakité', "jason.timbuktu.diakite"],
        [u'Matlagning del 1 av 10 - R\xe4ksm\xf6rg\xe5s | SVT Play',
         'matlagning.del.1.av.10-raksmorgas.svt.play'],
        ['$FOOBAR', "foobar"],
    ]

    def test(self):
        for inp, ref in self.test_values:
            self.assertEqual(filenamify(inp), ref)
