#!/usr/bin/env python3
import glob
import logging
import os
import re
import subprocess
import sys
from datetime import datetime


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cibuild")


twine_username = os.environ.get("TWINE_USERNAME")
twine_password = os.environ.get("TWINE_PASSWORD")
docker_username = os.environ.get("DOCKER_USERNAME")
docker_password = os.environ.get("DOCKER_PASSWORD")
aws_creds = os.environ.get("AWS_ACCESS_KEY_ID")


def tag():
    match = re.search("refs/tags/(.*)", os.environ.get("GITHUB_REF"))
    if match:
        return match.group(1)
    return None


def branch():
    match = re.search("refs/heads/(.*)", os.environ.get("GITHUB_REF"))
    if match:
        return match.group(1)
    return None


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
    for file in ["svtplay-dl", "svtplay-dl-amd64.zip", "svtplay-dl-win32.zip"]:
        if os.path.isfile(file):
            subprocess.check_call(
                ["aws", "--region", "us-east-1", "s3", "cp", "{}".format(file), "s3://svtplay-dl/{}/{}/{}".format(folder, version, file)],
            )


def pypi_upload():
    logger.info("Uploading to pypi")
    sdist = glob.glob("dist/svtplay-dl-*.tar.gz")
    if sdist:
        subprocess.check_call(["twine", "upload", sdist[0]])
    else:
        logging.warning("Can't find file for pypi..")


logger.info("Branch: {}".format(branch()))
logger.info("Tag: {}".format(tag()))

if not tag() and branch() != "master":
    sys.exit(0)

if os.environ.get("CIBUILD") != "yes":
    sys.exit(0)

if os.environ.get("OS").startswith("ubuntu") and os.environ.get("BUILD_DOCKER") == "yes":
    build_docker()

aws_upload()

if tag() and os.environ.get("OS").startswith("ubuntu"):
    pypi_upload()
