#!/usr/bin/env python3
import argparse
import glob
import logging
import os
import subprocess
import sys
from datetime import datetime

if sys.version_info[0] == 3 and sys.version_info[1] < 7:
    from backports.datetime_fromisoformat import MonkeyPatch

    MonkeyPatch.patch_fromisoformat()


root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cibuild")


parser = argparse.ArgumentParser(prog="cibuild")
general = parser.add_argument_group()
general.add_argument("-s", "--snapshots", action="store_true", dest="snapshot", default=False)
general.add_argument("-r", "--release", action="store_true", dest="release", default=False)
options = parser.parse_args()


twine_username = os.environ.get("TWINE_USERNAME")
twine_password = os.environ.get("TWINE_PASSWORD")
docker_username = os.environ.get("DOCKER_USERNAME")
docker_password = os.environ.get("DOCKER_PASSWORD")
aws_creds = os.environ.get("AWS_ACCESS_KEY_ID")

travis = os.environ.get("TRAVIS", "")
travis_tag = os.environ.get("TRAVIS_TAG", "")
travis_branch = os.environ.get("TRAVIS_BRANCH", "")
appveyor_tag = os.environ.get("APPVEYOR_REPO_TAG_NAME", "")
appveyor_branch = os.environ.get("APPVEYOR_REPO_BRANCH", "")


def tag():
    return travis_tag or appveyor_tag


def branch():
    return travis_branch or appveyor_branch


def docker_name(version):
    return "spaam/svtplay-dl:{}".format(version)


def build_docker():
    logger.info("Building docker")
    if tag():
        version = tag()
    else:
        version = "dev"

    subprocess.check_output(["docker", "build", "-f", "dockerfile/Dockerfile", "-t", docker_name(version), "."])
    subprocess.check_call(["docker", "login", "-u", docker_username, "-p", docker_password])
    subprocess.check_call(["docker", "push", docker_name(version)])

    if tag():
        subprocess.check_output(["docker", "tag", docker_name(version), docker_name("latest")])
        subprocess.check_call(["docker", "push", docker_name("latest")])


def build_package():
    logger.info("Building python package")

    subprocess.check_output(["python", "setup.py", "sdist", "bdist_wheel"])


def snapshot_folder():
    """
    Use the commit date in UTC as folder name
    """
    logger.info("Snapshot folder")
    try:
        stdout = subprocess.check_output(["git", "show", "-s", "--format=%cI", "HEAD"])
    except subprocess.CalledProcessError as e:
        logger.error("Error: {}".format(e.output.decode("ascii", "ignore").strip()))
        sys.exit(2)
    except FileNotFoundError as e:
        logger.error("Error: {}".format(e))
        sys.exit(2)
    ds = stdout.decode("ascii", "ignore").strip()
    dt = datetime.fromisoformat(ds)
    utc = dt - dt.utcoffset()
    return utc.strftime("%Y%m%d_%H%M%S")


def aws_upload():
    if tag():
        folder = "release"
        version = tag()
    else:
        folder = "snapshots"
        version = snapshot_folder()
    logger.info("Upload to aws {}/{}".format(folder, version))
    for file in ["svtplay-dl", "svtplay-dl.zip"]:
        if os.path.isfile(file):
            subprocess.check_call(["aws", "s3", "cp", "{}".format(file), "s3://svtplay-dl/{}/{}/{}".format(folder, version, file)])


def pypi_upload():
    logger.info("Uploading to pypi")
    sdist = glob.glob(os.path.join("dist/", "svtplay_dl-*.tar.gz"))
    if sdist:
        subprocess.check_call(["twine", "upload", sdist[0]])
    else:
        logging.warning("Can't find file for pypi..")


logger.info("Branch: {}".format(branch()))
logger.info("Tag: {}".format(tag()))

if not tag() and branch() != "master":
    sys.exit(0)

build_package()
if travis:
    build_docker()
aws_upload()

if tag() and travis:
    pypi_upload()
