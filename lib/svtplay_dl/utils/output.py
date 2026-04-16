import logging
import os
import pathlib
import re
import sys
import time
from datetime import timedelta

from svtplay_dl.utils.terminal import get_terminal_size
from svtplay_dl.utils.text import decode_html_entities
from svtplay_dl.utils.text import ensure_unicode
from svtplay_dl.utils.text import filenamify

progress_stream = sys.stderr


class ETA:
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


def progress(byte, total, extra=""):
    """Print some info about how much we have downloaded"""
    if total == 0:
        progresstr = f"Downloaded {byte >> 10}kB bytes"
        progress_stream.write(progresstr + "\r")
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
    width = get_terminal_size()[0] - 40
    rel_pos = int(float(pos) / total * width)
    bar = "".join(["=" * rel_pos, "." * (width - rel_pos)])

    # Determine how many digits in total (base 10)
    digits_total = len(str(total))
    fmt_width = "%0" + str(digits_total) + "d"
    fmt = "\r[" + fmt_width + "/" + fmt_width + "][%s] %s"

    progress_stream.write(fmt % (pos, total, bar, msg))


def filename(stream):
    if stream.output["title"] is None:
        data = ensure_unicode(stream.get_urldata())
        if data is None:
            return False
        match = re.search(r"(?i)<title[^>]*>\s*(.*?)\s*</title>", data, re.S)
        if match:
            stream.config.set("output_auto", True)
            title_tag = decode_html_entities(match.group(1))
            stream.output["title"] = filenamify(title_tag)
    return True


def sanitize(name):
    dirname = name.parent
    basename = str(name.name)
    blocklist = [":", "*", "?", '"', "<", ">", "|", "\0"]
    for i in blocklist:
        if i in basename:
            basename = basename.replace(i, "")

    return dirname.joinpath(basename.replace("..", "."))


def formatname(output, config):
    name = pathlib.Path(_formatname(output, config))
    subfolder = None
    dirname = None

    if not output.get("basedir", False):
        # If tvshow have not been derived by service do it by if season and episode is set
        if output.get("tvshow", None) is None:
            tvshow = output.get("season", None) is not None and output.get("episode", None) is not None
        else:
            tvshow = output.get("tvshow", False)
        if config.get("subfolder") and "title" in output and tvshow:
            # Add subfolder with name title
            subfolder = sanitize(pathlib.Path(filenamify(output["title"])))
        elif config.get("subfolder") and not tvshow:
            # Add subfolder with name movies
            subfolder = pathlib.Path("movies")
    if config.get("output") and pathlib.Path(config.get("output")).expanduser().is_dir():
        dirname = pathlib.Path(config.get("output"))
    elif config.get("path") and pathlib.Path(config.get("path")).expanduser().is_dir():
        dirname = pathlib.Path(config.get("path")).expanduser()
    elif config.get("output"):
        if "ext" in output and output["ext"]:
            name = pathlib.Path(f"{config.get('output')}.{output['ext']}").expanduser()
        else:
            name = pathlib.Path(config.get("output")).expanduser()
    name = pathlib.Path(sanitize(name.expanduser()))
    if subfolder and dirname:
        return dirname / subfolder / name.expanduser()
    elif subfolder:
        return subfolder / name.expanduser()
    elif dirname:
        return dirname / name.expanduser()
    else:
        return name.expanduser()


def _formatname(output, config):
    name = config.get("filename")
    # Handle the s{season}e{episode} block as a single unit (only when both present together)
    season = f"{int(output['season']):02d}" if output.get("season") else None
    episode = f"{int(output['episode']):02d}" if output.get("episode") else None

    if season and episode:
        name = re.sub(r"([sS])\{season\}([eE])\{episode\}", lambda m: f"{m.group(1)}{season}{m.group(2)}{episode}", name)
    elif season:
        name = re.sub(r"([sS])\{season\}([eE])\{episode\}", lambda m: f"{m.group(1)}{season}", name)
    elif episode:
        name = re.sub(r"([sS])\{season\}([eE])\{episode\}", lambda m: f"{m.group(2)}{episode}", name)
    else:
        name = re.sub(r"[\s\-\.]+[sS]\{season\}[eE]\{episode\}", "", name)

    if season:
        name = re.sub(r"([sS])?\{season\}", lambda m: f"{m.group(1) or ''}{season}", name)
    else:
        name = re.sub(r"[\s\-\.]*[sS]?\{season\}", "", name)

    if episode:
        name = re.sub(r"([eE])?\{episode\}", lambda m: f"{m.group(1) or ''}{episode}", name)
    else:
        name = re.sub(r"[\s\-\.]*[eE]?\{episode\}", "", name)

    if output.get("ext"):
        if "{ext}" in name:
            name = name.replace("{ext}", output["ext"])
        else:
            name = f"{name}.{output['ext']}"

    replacements = {}
    if output.get("title"):
        replacements["title"] = filenamify(output["title"])
    if output.get("episodename"):
        replacements["episodename"] = filenamify(output["episodename"])
    if output.get("id"):
        replacements["id"] = output["id"]
    if output.get("service"):
        replacements["service"] = output["service"]

    for key, value in replacements.items():
        name = name.replace(f"{{{key}}}", value)

    # Remove any remaining unavailable placeholders and their separators
    name = re.sub(r"[\s\-\.]+\{[\w\-]+\}|\{[\w\-]+\}[\s\-\.]*", "", name)

    # Clean up duplicate or leading/trailing separators
    name = re.sub(r"[\s\-]{2,}", " ", name)
    name = re.sub(r"^[\s\-\.]+|[\s\-\.]+$", "", name)

    return name


def find_dupes(output, config, video=True):
    otherfiles = [".srt", ".smi", ".tt", ".sami", ".wrst", ".tbn", ".nfo"]
    name = formatname(output, config)

    logging.info("Outfile: %s", name.name)
    if name.is_file() and not config.get("force"):
        return True, name
    # dir = os.path.dirname(os.path.realpath(name))
    if not name.parent.is_dir():
        # Create directory, needed for creating tvshow subfolder
        os.makedirs(name.parent)

    if video:
        files = [f for f in name.parent.glob("*.*") if f.is_file()]
        for i in files:
            lsname, lsext = os.path.splitext(i.name)
            if lsext in otherfiles:
                continue
            if lsname == str(name.stem) and not config.get("force"):
                return True, name
    return False, None
