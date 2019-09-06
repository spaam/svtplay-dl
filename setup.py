import os
import sys

from setuptools import find_packages
from setuptools import setup

import versioneer

srcdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib/")
sys.path.insert(0, srcdir)

vi = sys.version_info
if vi < (3, 4):
    raise RuntimeError("svtplay-dl requires Python 3.4 or greater")

about = {}
with open(os.path.join(srcdir, "svtplay_dl", "__version__.py"), "r") as f:
    exec(f.read(), about)

deps = []
deps.append("requests>=2.0.0")
deps.append("PySocks")
deps.append("cryptography")
deps.append("pyyaml")
deps.append("python-dateutil")

setup(
    name="svtplay-dl",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=find_packages("lib", exclude=["tests", "*.tests", "*.tests.*"]),
    install_requires=deps,
    package_dir={"": "lib"},
    scripts=["bin/svtplay-dl"],
    author="Johan Andersson",
    author_email="j@i19.se",
    description="Command-line program to download videos from various video on demand sites",
    license="MIT",
    url="https://svtplay-dl.se",
    python_requires=">=3.4",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Multimedia :: Sound/Audio",
        "Topic :: Multimedia :: Video",
        "Topic :: Utilities",
    ],
)
