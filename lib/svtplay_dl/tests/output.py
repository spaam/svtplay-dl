#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# The unittest framwork doesn't play nice with pylint:
#   pylint: disable-msg=C0103

from __future__ import absolute_import
import unittest
import svtplay_dl.output

class mockfile(object):
    def __init__(self):
        self.content = []

    def write(self, string):
        self.content.append(string)

    def read(self):
        return self.content.pop()

class progressbarTest(unittest.TestCase):
    def setUp(self):
        self.mockfile = mockfile()
        svtplay_dl.output.progress_stream = self.mockfile

    def test_0_100(self):
        svtplay_dl.output.progressbar(100, 0)
        self.assertEqual(
        self.mockfile.read(),
        "\r[000/100][..................................................] "
    )

    def test_progress_1_100(self):
        svtplay_dl.output.progressbar(100, 1)
        self.assertEqual(
        self.mockfile.read(),
        "\r[001/100][..................................................] "
    )

    def test_progress_2_100(self):
        svtplay_dl.output.progressbar(100, 2)
        self.assertEqual(
        self.mockfile.read(),
        "\r[002/100][=.................................................] "
    )

    def test_progress_50_100(self):
        svtplay_dl.output.progressbar(100, 50)
        self.assertEqual(
        self.mockfile.read(),
        "\r[050/100][=========================.........................] "
    )

    def test_progress_100_100(self):
        svtplay_dl.output.progressbar(100, 100)
        self.assertEqual(
        self.mockfile.read(),
        "\r[100/100][==================================================] "
    )

    def test_progress_20_100_msg(self):
        svtplay_dl.output.progressbar(100, 20, "msg")
        self.assertEqual(
        self.mockfile.read(),
        "\r[020/100][==========........................................] msg"
    )
