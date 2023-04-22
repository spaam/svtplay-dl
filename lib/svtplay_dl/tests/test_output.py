#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
# The unittest framework doesn't play nice with pylint:
#   pylint: disable-msg=C0103
import unittest
from unittest.mock import patch

import svtplay_dl.utils.output


# FIXME: use mock framework instead of this hack
class mockfile:
    def __init__(self):
        self.content = []

    def write(self, string):
        self.content.append(string)

    def read(self):
        return self.content.pop()


class progressTest(unittest.TestCase):
    def setUp(self):
        self.mockfile = mockfile()
        svtplay_dl.utils.output.progress_stream = self.mockfile

    @patch("svtplay_dl.utils.output.progressbar")
    def test_0_0(self, pbar):
        svtplay_dl.utils.output.progress(0, 0)
        assert not pbar.called

    @patch("svtplay_dl.utils.output.progressbar")
    def test_0_100(self, pbar):
        svtplay_dl.utils.output.progress(0, 100)
        pbar.assert_any_call(100, 0, "")


class progressbarTest(unittest.TestCase):
    def setUp(self):
        self.old_termsiz = svtplay_dl.utils.output.get_terminal_size
        svtplay_dl.utils.output.get_terminal_size = lambda: (50, 25)

        self.mockfile = mockfile()
        svtplay_dl.utils.output.progress_stream = self.mockfile

    def tearDown(self):
        svtplay_dl.utils.output.get_terminal_size = self.old_termsiz

    def test_0_100(self):
        svtplay_dl.utils.output.progressbar(100, 0)
        assert self.mockfile.read() == "\r[000/100][..........] "

    def test_progress_1_100(self):
        svtplay_dl.utils.output.progressbar(100, 1)
        assert self.mockfile.read() == "\r[001/100][..........] "

    def test_progress_2_100(self):
        svtplay_dl.utils.output.progressbar(100, 2)
        assert self.mockfile.read() == "\r[002/100][..........] "

    def test_progress_50_100(self):
        svtplay_dl.utils.output.progressbar(100, 50)
        assert self.mockfile.read() == "\r[050/100][=====.....] "

    def test_progress_100_100(self):
        svtplay_dl.utils.output.progressbar(100, 100)
        assert self.mockfile.read() == "\r[100/100][==========] "

    def test_progress_20_100_msg(self):
        svtplay_dl.utils.output.progressbar(100, 20, "msg")
        assert self.mockfile.read() == "\r[020/100][==........] msg"

    def test_progress_20_100_termwidth(self):
        svtplay_dl.utils.output.get_terminal_size = lambda: (75, 25)
        svtplay_dl.utils.output.progressbar(100, 20)
        assert self.mockfile.read() == "\r[020/100][=======............................] "


class EtaTest(unittest.TestCase):
    @patch("time.time")
    def test_eta_0_100(self, mock_time):
        mock_time.return_value = float(0)

        # Let's make this simple; we'll create something that
        # processes one item per second, and make the size be
        # 100.
        eta = svtplay_dl.utils.output.ETA(100)
        assert eta.left == 100  # no progress yet
        assert str(eta) == "(unknown)"  # no progress yet

        mock_time.return_value = float(10)  # sleep(10)
        eta.update(10)
        assert eta.left == 90
        assert str(eta) == "0:01:30"  # 90 items left, 90s left

        mock_time.return_value += 1
        eta.increment()  # another item completed in one second!
        assert eta.left == 89
        assert str(eta) == "0:01:29"

        mock_time.return_value += 9
        eta.increment(9)  # another item completed in one second!
        assert eta.left == 80
        assert str(eta) == "0:01:20"

        mock_time.return_value = float(90)  # sleep(79)
        eta.update(90)
        assert eta.left == 10
        assert str(eta) == "0:00:10"
