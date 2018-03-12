# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals

import sys
import logging

from svtplay_dl.utils.parser import parser, mergeparseroption, Options
from svtplay_dl.utils.getmedia import get_media, get_multiple_media

from svtplay_dl.service.cmore import Cmore

__version__ = "1.9.11"

log = logging.getLogger('svtplay_dl')


def setup_log(silent, verbose=False):
    logging.addLevelName(25, "INFO")
    fmt = '%(levelname)s: %(message)s'
    if silent:
        stream = sys.stderr
        level = 25
    elif verbose:
        stream = sys.stderr
        level = logging.DEBUG
        fmt = '%(levelname)s [%(created)s] %(filename)s/%(funcName)s: %(message)s'
    else:
        stream = sys.stdout
        level = logging.INFO

    logging.basicConfig(level=level, format=fmt)
    hdlr = logging.StreamHandler(stream)
    log.addHandler(hdlr)


def main():
    """ Main program """
    parse, options = parser(__version__)
    if options.exclude:
        options.exclude = options.exclude.split(",")
    if options.require_subtitle:
        if options.merge_subtitle:
            options.merge_subtitle = True
        else:
            options.subtitle = True
    if options.merge_subtitle:
        options.remux = True

    if options.silent_semi:
        options.silent = True

    if options.cmoreoperatorlist:
        c = Cmore(options, None)
        c.operatorlist()
        sys.exit(0)

    if options.proxy:
        options.proxy = options.proxy.replace("socks5", "socks5h", 1)
        options.proxy = dict(http=options.proxy,
                             https=options.proxy)

    if options.flexibleq and not options.quality:
        logging.error("flexible-quality requires a quality")

    if len(options.urls) == 0:
        parse.print_help()
        sys.exit(0)
    urls = options.urls
    options = mergeparseroption(Options(), options)
    if len(urls) < 1:
        parse.error("Incorrect number of arguments")
    setup_log(options.silent, options.verbose)

    try:
        if len(urls) == 1:
            get_media(urls[0], options, __version__)
        else:
            get_multiple_media(urls, options)
    except KeyboardInterrupt:
        print("")
