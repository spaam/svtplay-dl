# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import re
import os
import logging
from optparse import OptionParser

from svtplay_dl.log import log
from svtplay_dl.utils import get_http_data
from svtplay_dl.service import service_handler, Generic


__version__ = "0.9.2013.08.10"

class Options:
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
        self.quality = None
        self.flexibleq = None
        self.hls = False
        self.other = None
        self.subtitle = False
        self.username = None
        self.password = None

def get_media(url, options):
    stream = service_handler(url)
    if not stream:
        url, stream = Generic().get(url)
        url = url.replace("&amp;", "&")
    if not stream:
        log.error("That site is not supported. Make a ticket or send a message")
        sys.exit(2)

    if not options.output or os.path.isdir(options.output):
        data = get_http_data(url)
        match = re.search(r"(?i)<title.*>\s*(.*?)\s*</title>", data)
        if match:
            if sys.version_info > (3, 0):
                title = re.sub(r'[^\w\s-]', '', match.group(1)).strip().lower()
                if options.output:
                    options.output = options.output + re.sub(r'[-\s]+', '-', title)
                else:
                    options.output = re.sub(r'[-\s]+', '-', title)
            else:
                title = unicode(re.sub(r'[^\w\s-]', '', match.group(1)).strip().lower())
                if options.output:
                    options.output = unicode(options.output + re.sub(r'[-\s]+', '-', title))
                else:
                    options.output = unicode(re.sub(r'[-\s]+', '-', title))

    stream.get(options, url)

def setup_log(silent):
    if silent:
        stream = sys.stderr
        level = logging.WARNING
    else:
        stream = sys.stdout
        level = logging.INFO

    fmt = logging.Formatter('%(levelname)s %(message)s')
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
                      help="Enable for live streams")
    parser.add_option("-s", "--silent",
                      action="store_true", dest="silent", default=False)
    parser.add_option("-q", "--quality", default=0,
                      metavar="quality", help="Choose what format to download.\nIt will download the best format by default")
    parser.add_option("-Q", "--flexible-quality", default=0,
                      metavar="amount", dest="flexibleq", help="Allow given quality (as above) to differ by an amount.")
    parser.add_option("-H", "--hls",
                      action="store_true", dest="hls", default=False)
    parser.add_option("-S", "--subtitle",
                      action="store_true", dest="subtitle", default=False,
                      help="Download subtitle from the site if available.")
    parser.add_option("-u", "--username", default=None,
                      help="Username")
    parser.add_option("-p", "--password", default=None,
                      help="Password")
    (options, args) = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(0)
    if len(args) != 1:
        parser.error("incorrect number of arguments")

    setup_log(options.silent)

    if options.flexibleq and not options.quality:
        log.error("flexible-quality requires a quality")
        sys.exit(4)

    url = args[0]
    get_media(url, options)
