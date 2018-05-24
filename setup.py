from setuptools import setup, find_packages
import sys
import os

srcdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib/")
sys.path.insert(0, srcdir)

about = {}
with open(os.path.join(srcdir, 'svtplay_dl', '__version__.py'), 'r') as f:
    exec(f.read(), about)

deps = []
deps.append("requests>=2.0.0")
deps.append("PySocks")
deps.append("pycryptodome")
deps.append("pyyaml")

setup(
    name="svtplay-dl",
    version=about['__version__'],
    packages=find_packages(
        'lib',
        exclude=["tests", "*.tests", "*.tests.*"]),
    install_requires=deps,
    package_dir={'': 'lib'},
    scripts=['bin/svtplay-dl'],
    author=about["__author__"],
    author_email=about["__author_email__"],
    description="Command-line program to download videos from various video on demand sites",
    license=about["__license__"],
    url=about["__url__"],
    classifiers=["Development Status :: 5 - Production/Stable",
                 "Environment :: Console",
                 "Operating System :: POSIX",
                 "Operating System :: Microsoft :: Windows",
                 "Programming Language :: Python :: 3.4",
                 "Programming Language :: Python :: 3.5",
                 "Programming Language :: Python :: 3.6",
                 "Topic :: Internet :: WWW/HTTP",
                 "Topic :: Multimedia :: Sound/Audio",
                 "Topic :: Multimedia :: Video",
                 "Topic :: Utilities"],
    extras_require={"dev": [
        "flake8>=3.5, <3.6",
        "tox>=2.3, <3",
        "rstcheck>=2.2, <4.0"
    ]
    }
)
