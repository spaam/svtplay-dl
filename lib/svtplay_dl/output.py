# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import time
import re
import os
import io
from datetime import timedelta

from svtplay_dl.utils import is_py3
from svtplay_dl.utils.terminal import get_terminal_size
from svtplay_dl.log import log

progress_stream = sys.stderr

class ETA(object):
    """
    An ETA class, used to calculate how long it takes to process
    an arbitrary set of items. By initiating the object with the
    number of items and continuously updating with current
    progress, the class can calculate an estimation of how long
    time remains.
    """

    def __init__(self, end, start=0):
        """
        Parameters:
        end:   the end (or size, of start is 0)
        start: the starting position, defaults to 0
        """
        self.start = start
        self.end = end
        self.pos = start

        self.now = time.time()
        self.start_time = self.now

    def update(self, pos):
        """
        Set new absolute progress position.

        Parameters:
        pos: new absolute progress
        """
        self.pos = pos
        self.now = time.time()

    def increment(self, skip=1):
        """
        Like update, but set new pos relative to old pos.

        Parameters:
        skip: progress since last update (defaults to 1)
        """
        self.update(self.pos + skip)

    @property
    def left(self):
        """
        returns: How many item remains?
        """
        return self.end - self.pos

    def __str__(self):
        """
        returns: a time string of the format HH:MM:SS.
        """
        duration = self.now - self.start_time

        # Calculate how long it takes to process one item
        try:
            elm_time = duration / (self.end - self.left)
        except ZeroDivisionError:
            return "(unknown)"

        return str(timedelta(seconds=int(elm_time * self.left)))


def progress(byte, total, extra = ""):
    """ Print some info about how much we have downloaded """
    if total == 0:
        progresstr = "Downloaded %dkB bytes" % (byte >> 10)
        progress_stream.write(progresstr + '\r')
        return
    progressbar(total, byte, extra)

def progressbar(total, pos, msg=""):
    """
    Given a total and a progress position, output a progress bar
    to stderr. It is important to not output anything else while
    using this, as it relies soley on the behavior of carriage
    return (\\r).

    Can also take an optioal message to add after the
    progressbar. It must not contain newlines.

    The progress bar will look something like this:

    [099/500][=========...............................] ETA: 13:36:59

    Of course, the ETA part should be supplied be the calling
    function.
    """
    width = get_terminal_size()[0] - 35
    rel_pos = int(float(pos)/total*width)
    bar = ''.join(["=" * rel_pos, "." * (width - rel_pos)])

    # Determine how many digits in total (base 10)
    digits_total = len(str(total))
    fmt_width = "%0" + str(digits_total) + "d"
    fmt = "\r[" + fmt_width + "/" + fmt_width + "][%s] %s"

    progress_stream.write(fmt % (pos, total, bar, msg))

def output(options, filename, extention="mp4", openfd=True):
    if is_py3:
        file_d = io.IOBase
    else:
        file_d = file

    if options.output != "-":
        ext = re.search(r"(\.[a-z0-9]+)$", filename)
        if not ext:
            options.output = "%s.%s" % (options.output, extention)
        log.info("Outfile: %s", options.output)
        if (os.path.isfile(options.output) or \
            findexpisode(os.path.dirname(os.path.realpath(options.output)), options.service, os.path.basename(options.output))) and \
            not options.force:
            log.error("File already exists. Use --force to overwrite")
            return None
        if openfd:
            file_d = open(options.output, "wb")
    else:
        if openfd:
            if is_py3:
                file_d = sys.stdout.buffer
            else:
                file_d = sys.stdout

    return file_d

def findexpisode(directory, service, name):
    match = re.search("-(\w+)-\w+.(?!srt)\w{2,3}$", name)
    if not match:
        return False
    videoid = match.group(1)
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    for i in files:
        match = re.search("-(\w+)-\w+.(?!srt)\w{2,3}$", i)
        if match:
            if service:
                if name.find(service) and match.group(1) == videoid:
                    return True

    return False
