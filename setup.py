#!/usr/bin/env python
from setuptools import setup, find_packages
import sys

setup(
    name = "svtplay-dl",
    version = "0.9.2013.03.06",    # FIXME - extract from svtplay-dl
    packages = find_packages(
        'lib',
        exclude=["tests", "*.tests", "*.tests.*"]),
    package_dir = {'': 'lib'},
    scripts = ['svtplay-dl'],

    author = "Johan Andersson",
    author_email = "j@i19.se",
    description = "Command-line program to download videos from various video on demand sites",
    license = "MIT",
    url = "https://github.com/spaam/svtplay-dl",
)
