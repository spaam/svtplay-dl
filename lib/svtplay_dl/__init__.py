# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import os
import logging
import copy
import platform
from optparse import OptionParser

from svtplay_dl.error import UIException
from svtplay_dl.log import log
from svtplay_dl.utils import decode_html_entities, filenamify, select_quality
from svtplay_dl.service import service_handler, Generic
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle

__version__ = "0.9.2014.08.28"

class Options(object):
    """
    Options used when invoking the script from another Python script.

    Simple container class used when calling get_media() from another Python
    script. The variables corresponds to the command line parameters parsed
    in main() when the script is called directly.

    When called from a script there are a few more things to consider:

    * Logging is done to 'log'. main() calls setup_log() which sets the
      logging to either stdout or stderr depending on the silent level.
      A user calling get_media() directly can either also use setup_log()
      or configure the log manually.

    * Progress information is printed to 'progress_stream' which defaults to
      sys.stderr but can be changed to any stream.

    * Many errors results in calls to system.exit() so catch 'SystemExit'-
      Exceptions to prevent the entire application from exiting if that happens.
    """

    def __init__(self):
        self.output = None
        self.resume = False
        self.live = False
        self.silent = False
        self.force = False
        self.quality = 0
        self.flexibleq = None
        self.hls = False
        self.other = None
        self.subtitle = False
        self.username = None
        self.password = None
        self.thumbnail = False
        self.all_episodes = False
        self.force_subtitle = False
        self.preferred = None
        self.verbose = False
        self.output_auto = False
        self.service = None

def get_media(url, options):

    stream = service_handler(url)
    if not stream:
        url, stream = Generic().get(url)
    if not stream:
        log.error("That site is not supported. Make a ticket or send a message")
        sys.exit(2)

    if options.all_episodes:
        if options.output and not os.path.isdir(options.output):
            log.error("Output must be a directory if used with --all-episodes")
            sys.exit(2)

        episodes = stream.find_all_episodes(options)

        for idx, o in enumerate(episodes):
            if o == url:
                substream = stream
            else:
                substream = service_handler(o)

            log.info("Episode %d of %d", idx + 1, len(episodes))

            # get_one_media overwrites options.output...
            get_one_media(substream, copy.copy(options))
    else:
        get_one_media(stream, options)

def get_one_media(stream, options):
    if not options.output or os.path.isdir(options.output):
        data = stream.get_urldata()
        match = re.search(r"(?i)<title[^>]*>\s*(.*?)\s*</title>", data, re.S)
        if match:
            options.output_auto = True
            title_tag = decode_html_entities(match.group(1))
            if not options.output:
                options.output = filenamify(title_tag)
            else:
                # output is a directory
                options.output = os.path.join(options.output, filenamify(title_tag))

    if platform.system() == "Windows":
        # ugly hack. replace \ with / or add extra \ because c:\test\kalle.flv will add c:_tab_est\kalle.flv
        if options.output.find("\\") > 0:
            options.output = options.output.replace("\\", "/")

    videos = []
    subs = []
    streams = stream.get(options)
    if streams:
        for i in streams:
            if isinstance(i, VideoRetriever):
                if options.preferred:
                    if options.preferred == i.name():
                        videos.append(i)
                else:
                    videos.append(i)
            if isinstance(i, subtitle):
                subs.append(i)

        if options.subtitle and options.output != "-":
            if subs:
                subs[0].download(copy.copy(options))
            if options.force_subtitle:
                return

        if len(videos) > 0:
            stream = select_quality(options, videos)
            try:
                stream.download()
            except UIException as e:
                if options.verbose:
                    raise e
                log.error(e.message)
                sys.exit(2)

            if options.thumbnail:
                if hasattr(stream, "get_thumbnail"):
                    log.info("thumb requested")
                    if options.output != "-":
                        log.info("getting thumbnail")
                        stream.get_thumbnail(options)
            else:
                log.info("no thumb requested")
        else:
            log.error("Can't find any streams for that url")
    else:
        log.error("Can't find any streams for that url")


def setup_log(silent, verbose=False):
    fmt = logging.Formatter('%(levelname)s: %(message)s')
    if silent:
        stream = sys.stderr
        level = logging.WARNING
    elif verbose:
        stream = sys.stderr
        level = logging.DEBUG
        fmt = logging.Formatter('[%(created).3f] %(pathname)s/%(funcName)s: %(levelname)s %(message)s')
    else:
        stream = sys.stdout
        level = logging.INFO

    hdlr = logging.StreamHandler(stream)
    hdlr.setFormatter(fmt)

    log.addHandler(hdlr)
    log.setLevel(level)

def main():
    """ Main program """
    usage = "usage: %prog [options] url"
    parser = OptionParser(usage=usage, version=__version__)
    parser.add_option("-o", "--output",
                      metavar="OUTPUT", help="Outputs to the given filename.")
    parser.add_option("-r", "--resume",
                      action="store_true", dest="resume", default=False,
                      help="Resume a download")
    parser.add_option("-l", "--live",
                      action="store_true", dest="live", default=False,
                      help="Enable for live streams (RTMP based ones)")
    parser.add_option("-s", "--silent",
                      action="store_true", dest="silent", default=False)
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False)
    parser.add_option("-f", "--force",
                      action="store_true", dest="force", default=False)
    parser.add_option("-q", "--quality", default=0,
                      metavar="quality", help="Choose what format to download.\nIt will download the best format by default")
    parser.add_option("-Q", "--flexible-quality", default=0,
                      metavar="amount", dest="flexibleq", help="Allow given quality (as above) to differ by an amount.")
    parser.add_option("-H", "--hls",
                      action="store_true", dest="hls", default=False, help="obsolete use -P")
    parser.add_option("-S", "--subtitle",
                      action="store_true", dest="subtitle", default=False,
                      help="Download subtitle from the site if available.")
    parser.add_option("--force-subtitle", dest="force_subtitle", default=False,
                      action="store_true", help="Download only subtitle if its used with -S")
    parser.add_option("-u", "--username", default=None,
                      help="Username")
    parser.add_option("-p", "--password", default=None,
                      help="Password")
    parser.add_option("-t", "--thumbnail",
                      action="store_true", dest="thumbnail", default=False,
                      help="Download thumbnail from the site if available.")
    parser.add_option("-A", "--all-episodes",
                      action="store_true", dest="all_episodes", default=False,
                      help="Try to download all episodes.")
    parser.add_option("-P", "--preferred", default=None,
                      metavar="preferred", help="preferred download method (rtmp, hls or hds)")
    (options, args) = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(0)
    if len(args) != 1:
        parser.error("incorrect number of arguments")
    options = mergeParserOption(Options(), options)
    setup_log(options.silent, options.verbose)

    if options.flexibleq and not options.quality:
        log.error("flexible-quality requires a quality")
        sys.exit(4)

    url = args[0]

    try:
        get_media(url, options)
    except KeyboardInterrupt:
        print("")

def mergeParserOption(options, parser):
    options.output = parser.output
    options.resume = parser.resume
    options.live = parser.live
    options.silent = parser.silent
    options.force = parser.force
    options.quality = parser.quality
    options.flexibleq = parser.flexibleq
    options.hls = parser.hls
    options.subtitle = parser.subtitle
    options.username = parser.username
    options.password = parser.password
    options.thumbnail = parser.thumbnail
    options.all_episodes = parser.all_episodes
    options.force_subtitle = parser.force_subtitle
    options.preferred = parser.preferred
    options.verbose = parser.verbose
    return options
