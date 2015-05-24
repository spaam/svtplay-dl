# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import os
import logging
import copy
from optparse import OptionParser

from svtplay_dl.error import UIException
from svtplay_dl.log import log
from svtplay_dl.utils import select_quality, list_quality
from svtplay_dl.utils.urllib import URLError
from svtplay_dl.service import service_handler, Generic
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.output import filename

from svtplay_dl.service.aftonbladet import Aftonbladet
from svtplay_dl.service.bambuser import Bambuser
from svtplay_dl.service.bigbrother import Bigbrother
from svtplay_dl.service.dbtv import Dbtv
from svtplay_dl.service.disney import Disney
from svtplay_dl.service.dr import Dr
from svtplay_dl.service.expressen import Expressen
from svtplay_dl.service.facebook import Facebook
from svtplay_dl.service.hbo import Hbo
from svtplay_dl.service.justin import Justin
from svtplay_dl.service.kanal5 import Kanal5
from svtplay_dl.service.lemonwhale import Lemonwhale
from svtplay_dl.service.mtvnn import Mtvnn
from svtplay_dl.service.mtvservices import Mtvservices
from svtplay_dl.service.nrk import Nrk
from svtplay_dl.service.oppetarkiv import OppetArkiv
from svtplay_dl.service.picsearch import Picsearch
from svtplay_dl.service.qbrick import Qbrick
from svtplay_dl.service.radioplay import Radioplay
from svtplay_dl.service.ruv import Ruv
from svtplay_dl.service.raw import Raw
from svtplay_dl.service.sr import Sr
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.service.tv4play import Tv4play
from svtplay_dl.service.urplay import Urplay
from svtplay_dl.service.vg import Vg
from svtplay_dl.service.viaplay import Viaplay
from svtplay_dl.service.vimeo import Vimeo
from svtplay_dl.service.youplay import Youplay

__version__ = "0.10.2015.05.24"

sites = [
    Aftonbladet,
    Bambuser,
    Bigbrother,
    Dbtv,
    Disney,
    Dr,
    Expressen,
    Facebook,
    Hbo,
    Justin,
    Lemonwhale,
    Kanal5,
    Mtvservices,
    Mtvnn,
    Nrk,
    Qbrick,
    Picsearch,
    Ruv,
    Radioplay,
    Sr,
    Svtplay,
    OppetArkiv,
    Tv4play,
    Urplay,
    Viaplay,
    Vimeo,
    Vg,
    Youplay]

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
        self.list_quality = False
        self.hls = False
        self.other = None
        self.subtitle = False
        self.username = None
        self.password = None
        self.thumbnail = False
        self.all_episodes = False
        self.all_last = -1
        self.force_subtitle = False
        self.preferred = None
        self.verbose = False
        self.output_auto = False
        self.service = None
        self.cookies = None
        self.exclude = None

def get_media(url, options):

    stream = service_handler(sites, url)
    if not stream:
        try:
            url, stream = Generic().get(sites, url)
        except URLError as e:
            log.error("Cant find that page: %s", e.reason)
            return
    if not stream:
        if url.find(".f4m") > 0 or url.find(".m3u8") > 0:
            stream = Raw(url)
        if not stream:
            log.error("That site is not supported. Make a ticket or send a message")
            sys.exit(2)

    if options.all_episodes:
        if options.output and os.path.isfile(options.output):
            log.error("Output must be a directory if used with --all-episodes")
            sys.exit(2)
        elif options.output and not os.path.exists(options.output):
            try:
                os.makedirs(options.output)
            except OSError as e:
                log.error("%s: %s" % (e.strerror, e.filename))
                return

        episodes = stream.find_all_episodes(options)
        if episodes is None:
            return
        for idx, o in enumerate(episodes):
            if o == url:
                substream = stream
            else:
                substream = service_handler(sites, o)

            log.info("Episode %d of %d", idx + 1, len(episodes))

            try:
                # get_one_media overwrites options.output...
                get_one_media(substream, copy.copy(options))
            except URLError as e:
                log.error("Cant find that page: %s", e.reason)
                return
    else:
        try:
            get_one_media(stream, options)
        except URLError as e:
            log.error("Cant find that page: %s", e.reason)
            sys.exit(2)

def get_one_media(stream, options):
    # Make an automagic filename
    if not filename(options, stream):
        return

    videos = []
    subs = []
    streams = stream.get(options)
    for i in streams:
        if isinstance(i, VideoRetriever):
            if options.preferred:
                if options.preferred.lower() == i.name():
                    videos.append(i)
            else:
                videos.append(i)
        if isinstance(i, subtitle):
            subs.append(i)

    if options.subtitle and options.output != "-":
        if subs:
            subs[0].download()
        if options.force_subtitle:
            return

    if len(videos) == 0:
        log.error("Can't find any streams for that url")
    else:
        if options.list_quality:
            list_quality(videos)
            return
        stream = select_quality(options, videos)
        log.info("Selected to download %s, bitrate: %s",
                 stream.name(), stream.bitrate)
        if options.get_url:
            print(stream.url)
            return
        try:
            stream.download()
        except UIException as e:
            if options.verbose:
                raise e
            log.error(e.message)
            sys.exit(2)

        if options.thumbnail and hasattr(stream, "get_thumbnail"):
            if options.output != "-":
                log.info("Getting thumbnail")
                stream.get_thumbnail(options)
            else:
                log.warning("Can not get thumbnail when fetching to stdout")


def setup_log(silent, verbose=False):
    fmt = logging.Formatter('%(levelname)s: %(message)s')
    if silent:
        stream = sys.stderr
        level = logging.WARNING
    elif verbose:
        stream = sys.stderr
        level = logging.DEBUG
        fmt = logging.Formatter('%(levelname)s [%(created)s] %(pathname)s/%(funcName)s: %(message)s')
    else:
        stream = sys.stdout
        level = logging.INFO

    hdlr = logging.StreamHandler(stream)
    hdlr.setFormatter(fmt)

    log.addHandler(hdlr)
    log.setLevel(level)

def main():
    """ Main program """
    usage = "Usage: %prog [options] url"
    parser = OptionParser(usage=usage, version=__version__)
    parser.add_option("-o", "--output",
                      metavar="OUTPUT", help="outputs to the given filename")
    parser.add_option("-f", "--force",
                      action="store_true", dest="force", default=False,
                      help="overwrite if file exists already")
    parser.add_option("-r", "--resume",
                      action="store_true", dest="resume", default=False,
                      help="resume a download (RTMP based ones)")
    parser.add_option("-l", "--live",
                      action="store_true", dest="live", default=False,
                      help="enable for live streams (RTMP based ones)")
    parser.add_option("-s", "--silent",
                      action="store_true", dest="silent", default=False,
                      help="be less verbose")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="explain what is going on")
    parser.add_option("-q", "--quality", default=0,
                      metavar="quality", help="choose what format to download based on bitrate / video resolution."
                                              "it will download the best format by default")
    parser.add_option("-Q", "--flexible-quality", default=0,
                      metavar="amount", dest="flexibleq", help="allow given quality (as above) to differ by an amount")
    parser.add_option("--list-quality", dest="list_quality", action="store_true", default=False,
                      help="list the quality for a video")
    parser.add_option("-H", "--hls",
                      action="store_true", dest="hls", default=False, help="obsolete use -P hls")
    parser.add_option("-S", "--subtitle",
                      action="store_true", dest="subtitle", default=False,
                      help="download subtitle from the site if available")
    parser.add_option("--force-subtitle", dest="force_subtitle", default=False,
                      action="store_true", help="download only subtitle if its used with -S")
    parser.add_option("-u", "--username", default=None,
                      help="username")
    parser.add_option("-p", "--password", default=None,
                      help="password")
    parser.add_option("-t", "--thumbnail",
                      action="store_true", dest="thumbnail", default=False,
                      help="download thumbnail from the site if available")
    parser.add_option("-A", "--all-episodes",
                      action="store_true", dest="all_episodes", default=False,
                      help="try to download all episodes")
    parser.add_option("--all-last", dest="all_last", default=-1, type=int,
                      metavar="NN", help="get last NN episodes instead of all episodes")
    parser.add_option("-P", "--preferred", default=None,
                      metavar="preferred", help="preferred download method (rtmp, hls or hds)")
    parser.add_option("--exclude", dest="exclude", default=None,
                      metavar="WORD1,WORD2,...", help="exclude videos with the WORD(s) in the filename. comma separated.")
    parser.add_option("-g", "--get-url",
                      action="store_true", dest="get_url", default=False,
                      help="do not download any video, but instead print the URL.")
    (options, args) = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(0)
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    if options.exclude:
        options.exclude = options.exclude.split(",")
    if options.force_subtitle:
        options.subtitle = True
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
    options.list_quality = parser.list_quality
    options.hls = parser.hls
    options.subtitle = parser.subtitle
    options.username = parser.username
    options.password = parser.password
    options.thumbnail = parser.thumbnail
    options.all_episodes = parser.all_episodes
    options.all_last = parser.all_last
    options.force_subtitle = parser.force_subtitle
    options.preferred = parser.preferred
    options.verbose = parser.verbose
    options.exclude = parser.exclude
    options.get_url = parser.get_url
    return options
