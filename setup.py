from setuptools import setup, find_packages
import sys
import os

srcdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib/")
sys.path.insert(0, srcdir)
import svtplay_dl

deps = []

if sys.version_info[0] == 2 and sys.version_info[1] <= 7 and sys.version_info[2] < 9:
    deps.append("requests>=2.0.0")
    deps.append("PySocks")
    deps.append("pyOpenSSL")
    deps.append("ndg-httpsclient")
    deps.append("pyasn1")
else:
    deps.append(["requests>=2.0.0"])
    deps.append("PySocks")

setup(
    name="svtplay-dl",
    version=svtplay_dl.__version__,
    packages=find_packages(
        'lib',
        exclude=["tests", "*.tests", "*.tests.*"]),
    install_requires=deps,
    package_dir={'': 'lib'},
    scripts=['bin/svtplay-dl'],
    author="Johan Andersson",
    author_email="j@i19.se",
    description="Command-line program to download videos from various video on demand sites",
    license="MIT",
    url="https://svtplay-dl.se",
    classifiers=["Development Status :: 5 - Production/Stable",
                 "Environment :: Console",
                 "Operating System :: POSIX",
                 "Operating System :: Microsoft :: Windows",
                 "Programming Language :: Python :: 2.6",
                 "Programming Language :: Python :: 2.7",
                 "Programming Language :: Python :: 3.3",
                 "Programming Language :: Python :: 3.4",
                 "Programming Language :: Python :: 3.5",
                 "Topic :: Internet :: WWW/HTTP",
                 "Topic :: Multimedia :: Sound/Audio",
                 "Topic :: Multimedia :: Video",
                 "Topic :: Utilities"]
)
