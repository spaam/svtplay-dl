#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8
# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103
import unittest

from svtplay_dl.utils.parser import setup_defaults
from svtplay_dl.utils.text import decode_html_entities
from svtplay_dl.utils.text import ensure_unicode
from svtplay_dl.utils.text import exclude
from svtplay_dl.utils.text import filenamify


class filenamifyTest(unittest.TestCase):
    test_values = [
        ["foo", "foo"],
        ["foo bar", "foo.bar"],
        ["FOO BAR", "foo.bar"],
        ["foo-bar baz", "foo-bar.baz"],
        ['Jason "Timbuktu" Diakité', "jason.timbuktu.diakite"],
        ["Matlagning del 1 av 10 - R\xe4ksm\xf6rg\xe5s | SVT Play", "matlagning.del.1.av.10-raksmorgas.svt.play"],
        ["$FOOBAR", "foobar"],
    ]

    def test(self):
        for inp, ref in self.test_values:
            assert filenamify(inp) == ref

    def test_exclude_true(self):
        config = setup_defaults()
        config.set("exclude", "hej")
        assert exclude(config, "hejsanhoppsan")

    def test_exclude_false(self):
        config = setup_defaults()
        config.set("exclude", "hej")
        assert not exclude(config, "hoppsan")

    def test_exlude_default(self):
        config = setup_defaults()
        assert not exclude(config, "hoppsan")

    def test_ensure_unicode(self):
        assert ensure_unicode(b"hello") == "hello"

    def test_decode_html(self):
        assert decode_html_entities("&lt;3 &amp;") == "<3 &"
