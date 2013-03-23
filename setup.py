#!/usr/bin/env python
from setuptools import setup, find_packages
import sys
import os

srcdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib/")
sys.path.insert(0, srcdir)
import svtplay_dl

setup(
    name = "svtplay-dl",
    version = svtplay_dl.__version__,
    packages = find_packages(
        'lib',
        exclude=["tests", "*.tests", "*.tests.*"]),
    package_dir = {'': 'lib'},
    scripts = ['bin/svtplay-dl'],

    author = "Johan Andersson",
    author_email = "j@i19.se",
    description = "Command-line program to download videos from various video on demand sites",
    license = "MIT",
    url = "https://github.com/spaam/svtplay-dl",
)
