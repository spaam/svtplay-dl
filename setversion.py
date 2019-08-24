#
#  This set the version using git. useful when building with cx_freeze
#
import re
import subprocess

cmd = ["git", "describe", "--tags", "--dirty", "--always"]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
stdout, stderr = p.communicate()
version = stdout.decode().strip()

initfile = "lib/svtplay_dl/__init__.py"
with open(initfile) as fd:
    data = fd.read()

newstring = re.sub("(__version__ = get_version[^\n]+)", '__version__ = "{}"'.format(version), data)
with open(initfile, "wt") as fd:
    fd.write(newstring)
