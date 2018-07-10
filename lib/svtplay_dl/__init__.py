# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals

import sys
import logging
import yaml

from svtplay_dl.utils.parser import setup_defaults, parser, parsertoconfig
from svtplay_dl.utils.getmedia import get_media, get_multiple_media
from svtplay_dl.service.cmore import Cmore

from .__version__ import get_versions
__version__ = get_versions()['version']
del get_versions


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
        fmt = '%(levelname)s [%(created)s] %(pathname)s/%(funcName)s: %(message)s'
    else:
        stream = sys.stdout
        level = logging.INFO

    logging.basicConfig(level=level, format=fmt)
    hdlr = logging.StreamHandler(stream)
    log.addHandler(hdlr)


def main():
    """ Main program """
    parse, options = parser(__version__)

    if options.cmoreoperatorlist:
        c = Cmore(options, None)
        c.operatorlist()
        sys.exit(0)

    if options.flexibleq and not options.quality:
        logging.error("flexible-quality requires a quality")

    if len(options.urls) == 0:
        parse.print_help()
        sys.exit(0)
    urls = options.urls
    config = parsertoconfig(setup_defaults(), options)
    if len(urls) < 1:
        parse.error("Incorrect number of arguments")
    setup_log(config.get("silent"), config.get("verbose"))

    try:
        if len(urls) == 1:
            get_media(urls[0], config, __version__)
        else:
            get_multiple_media(urls, config)
    except KeyboardInterrupt:
        print("")
    except (yaml.YAMLError, yaml.MarkedYAMLError) as e:
        logging.error('Your settings file(s) contain invalid YAML syntax! Please fix and restart!, {}'.format(str(e)))
        sys.exit(2)
