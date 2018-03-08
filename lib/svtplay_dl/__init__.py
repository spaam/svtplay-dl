# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import, unicode_literals

import sys
import os
import logging
import copy
import re
from optparse import OptionParser

from svtplay_dl.error import UIException
from svtplay_dl.log import log
from svtplay_dl.utils import select_quality, list_quality, is_py2, ensure_unicode
from svtplay_dl.service import service_handler, Generic
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.output import filename
from svtplay_dl.postprocess import postprocess

from svtplay_dl.service.aftonbladet import Aftonbladet, Aftonbladettv
from svtplay_dl.service.atg import Atg
from svtplay_dl.service.bambuser import Bambuser
from svtplay_dl.service.bigbrother import Bigbrother
from svtplay_dl.service.cmore import Cmore
from svtplay_dl.service.dbtv import Dbtv
from svtplay_dl.service.disney import Disney
from svtplay_dl.service.dplay import Dplay
from svtplay_dl.service.dr import Dr
from svtplay_dl.service.efn import Efn
from svtplay_dl.service.eurosport import Eurosport
from svtplay_dl.service.expressen import Expressen
from svtplay_dl.service.facebook import Facebook
from svtplay_dl.service.filmarkivet import Filmarkivet
from svtplay_dl.service.flowonline import Flowonline
from svtplay_dl.service.hbo import Hbo
from svtplay_dl.service.twitch import Twitch
from svtplay_dl.service.lemonwhale import Lemonwhale
from svtplay_dl.service.mtvnn import MtvMusic
from svtplay_dl.service.mtvnn import Mtvnn
from svtplay_dl.service.mtvservices import Mtvservices
from svtplay_dl.service.nhl import NHL
from svtplay_dl.service.nrk import Nrk
from svtplay_dl.service.oppetarkiv import OppetArkiv
from svtplay_dl.service.picsearch import Picsearch
from svtplay_dl.service.pokemon import Pokemon
from svtplay_dl.service.qbrick import Qbrick
from svtplay_dl.service.radioplay import Radioplay
from svtplay_dl.service.riksdagen import Riksdagen
from svtplay_dl.service.ruv import Ruv
from svtplay_dl.service.raw import Raw
from svtplay_dl.service.solidtango import Solidtango
from svtplay_dl.service.sportlib import Sportlib
from svtplay_dl.service.sr import Sr
from svtplay_dl.service.svt import Svt
from svtplay_dl.service.barnkanalen import Barnkanalen
from svtplay_dl.service.svtplay import Svtplay
from svtplay_dl.service.tv4play import Tv4play
from svtplay_dl.service.urplay import Urplay
from svtplay_dl.service.vg import Vg
from svtplay_dl.service.viaplay import Viaplay
from svtplay_dl.service.viasatsport import Viasatsport
from svtplay_dl.service.vimeo import Vimeo
from svtplay_dl.service.youplay import Youplay

__version__ = "1.9.10"

sites = [
    Aftonbladet,
    Aftonbladettv,
    Atg,
    Bambuser,
    Barnkanalen,
    Bigbrother,
    Cmore,
    Dbtv,
    Disney,
    Dplay,
    Dr,
    Efn,
    Eurosport,
    Expressen,
    Facebook,
    Filmarkivet,
    Flowonline,
    Hbo,
    Twitch,
    Lemonwhale,
    Mtvservices,
    MtvMusic,
    Mtvnn,
    NHL,
    Nrk,
    Qbrick,
    Picsearch,
    Pokemon,
    Ruv,
    Radioplay,
    Solidtango,
    Sportlib,
    Sr,
    Svt,
    Svtplay,
    OppetArkiv,
    Tv4play,
    Urplay,
    Viaplay,
    Viasatsport,
    Vimeo,
    Vg,
    Youplay,
    Riksdagen,
    Raw]


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
        self.capture_time = -1
        self.silent = False
        self.force = False
        self.quality = 0
        self.flexibleq = 0
        self.list_quality = False
        self.other = None
        self.subtitle = False
        self.username = None
        self.password = None
        self.thumbnail = False
        self.all_episodes = False
        self.all_last = -1
        self.merge_subtitle = False
        self.force_subtitle = False
        self.require_subtitle = False
        self.get_all_subtitles = False
        self.get_raw_subtitles = False
        self.convert_subtitle_colors = False
        self.preferred = None
        self.verbose = False
        self.output_auto = False
        self.service = None
        self.cookies = None
        self.exclude = None
        self.get_url = False
        self.ssl_verify = True
        self.http_headers = None
        self.stream_prio = None
        self.remux = False
        self.silent_semi = False
        self.proxy = None
        self.hls_time_stamp = False


def get_multiple_media(urls, options):
    if options.output and os.path.isfile(options.output):
        log.error("Output must be a directory if used with multiple URLs")
        sys.exit(2)
    elif options.output and not os.path.exists(options.output):
        try:
            os.makedirs(options.output)
        except OSError as e:
            log.error("%s: %s", e.strerror, e.filename)
            return

    for url in urls:
        get_media(url, copy.copy(options))


def get_media(url, options):
    if "http" not in url[:4]:
        url = "http://%s" % url

    if options.silent_semi:
        options.silent = True
    if options.verbose:
        log.debug("version: {0}".format(__version__))
    stream = service_handler(sites, options, url)
    if not stream:
        generic = Generic(options, url)
        url, stream = generic.get(sites)
    if not stream:
        if re.search(".f4m", url) or re.search(".m3u8", url) or re.search(".mpd", url):
            stream = Raw(options, url)
        if not stream:
            log.error("That site is not supported. Make a ticket or send a message")
            sys.exit(2)

    if is_py2:
        url = ensure_unicode(url)

    if options.all_episodes:
        get_all_episodes(stream, copy.copy(options), url)
    else:
        get_one_media(stream, copy.copy(options))


def get_all_episodes(stream, options, url):
    if options.output and os.path.isfile(options.output):
        log.error("Output must be a directory if used with --all-episodes")
        sys.exit(2)
    elif options.output and not os.path.exists(options.output):
        try:
            os.makedirs(options.output)
        except OSError as e:
            log.error("%s: %s", e.strerror, e.filename)
            return

    episodes = stream.find_all_episodes(options)
    if episodes is None:
        return
    for idx, o in enumerate(episodes):
        if o == url:
            substream = stream
        else:
            substream = service_handler(sites, copy.copy(options), o)

        log.info("Episode %d of %d", idx + 1, len(episodes))
        log.info("Url: %s", o)

        # get_one_media overwrites options.output...
        get_one_media(substream, copy.copy(options))


def get_one_media(stream, options):
    # Make an automagic filename
    if not filename(stream):
        return

    if options.merge_subtitle:
        from svtplay_dl.utils import which
        if not which('ffmpeg'):
            log.error("--merge-subtitle needs ffmpeg. Please install ffmpeg.")
            log.info("https://ffmpeg.org/download.html")
            sys.exit(2)

    videos = []
    subs = []
    subfixes = []
    error = []
    streams = stream.get()
    try:
        for i in streams:
            if isinstance(i, VideoRetriever):
                if options.preferred:
                    if options.preferred.lower() == i.name():
                        videos.append(i)
                else:
                    videos.append(i)
            if isinstance(i, subtitle):
                subs.append(i)
            if isinstance(i, Exception):
                error.append(i)
    except Exception as e:
        if options.verbose:
            raise
        else:
            log.error("svtplay-dl crashed")
            log.error("Run again and add --verbose as an argument, to get more information")
            log.error("If the error persists, you can report it at https://github.com/spaam/svtplay-dl/issues")
            log.error("Include the URL used, the stack trace and the output of svtplay-dl --version in the issue")
        sys.exit(3)

    if options.require_subtitle and not subs:
        log.info("No subtitles available")
        return

    if options.subtitle and options.get_url:
        if subs:
            if options.get_all_subtitles:
                for sub in subs:
                    print(sub.url)
            else:
                print(subs[0].url)
        if options.force_subtitle:
            return

    def options_subs_dl(subfixes):
        if subs:
            if options.get_all_subtitles:
                for sub in subs:
                    sub.download()
                    if options.merge_subtitle:
                        if sub.subfix:
                            subfixes += [sub.subfix]
                        else:
                            options.get_all_subtitles = False
            else:
                subs[0].download()
        elif options.merge_subtitle:
            options.merge_subtitle = False

    if options.subtitle and options.output != "-" and not options.get_url:
        options_subs_dl(subfixes)
        if options.force_subtitle:
            return

    if options.merge_subtitle and not options.subtitle:
        options_subs_dl(subfixes)

    if not videos:
        log.error("No videos found.")
        for exc in error:
            log.error(str(exc))
    else:
        if options.list_quality:
            list_quality(videos)
            return
        try:
            stream = select_quality(options, videos)
            if options.get_url:
                print(stream.url)
                return
            log.info("Selected to download %s, bitrate: %s",
                     stream.name(), stream.bitrate)
            stream.download()
        except UIException as e:
            if options.verbose:
                raise e
            log.error(e)
            sys.exit(2)

        if options.thumbnail and hasattr(stream, "get_thumbnail"):
            if options.output != "-":
                log.info("Getting thumbnail")
                stream.get_thumbnail(options)
            else:
                log.warning("Can not get thumbnail when fetching to stdout")
        post = postprocess(stream, options, subfixes)

        if stream.name() == "dash" or (stream.name() == "hls" and stream.options.segments) and post.detect:
            post.merge()
        elif (stream.name() == "dash" or (stream.name() == "hls" and stream.options.segments)) and not post.detect and stream.finished:
            log.warning("Cant find ffmpeg/avconv. audio and video is in seperate files. if you dont want this use -P hls or hds")
        elif stream.name() == "hls" or options.remux:
            if post.detect:
                post.remux()
            else:
                log.warning("Cant find ffmpeg/avconv. File may be unplayable.")

        if options.silent_semi and stream.finished:
            log.log(25, "Download of %s was completed" % stream.options.output)


def setup_log(silent, verbose=False):
    logging.addLevelName(25, "INFO")
    fmt = logging.Formatter('%(levelname)s: %(message)s')
    if silent:
        stream = sys.stderr
        level = 25
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
    usage = "Usage: %prog [options] [urls]"
    parser = OptionParser(usage=usage, version=__version__)
    parser.add_option("-o", "--output",
                      metavar="OUTPUT", help="outputs to the given filename or folder")
    parser.add_option("-f", "--force",
                      action="store_true", dest="force", default=False,
                      help="overwrite if file exists already")
    parser.add_option("-r", "--resume",
                      action="store_true", dest="resume", default=False,
                      help="resume a download (RTMP based ones)")
    parser.add_option("-l", "--live",
                      action="store_true", dest="live", default=False,
                      help="enable for live streams (RTMP based ones)")
    parser.add_option("-c", "--capture_time", default=-1, type=int, metavar="capture_time",
                      help="define capture time in minutes of a live stream")
    parser.add_option("-s", "--silent",
                      action="store_true", dest="silent", default=False,
                      help="be less verbose")
    parser.add_option("--silent-semi", action="store_true",
                      dest="silent_semi", default=False, help="only show a message when the file is downloaded")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose", default=False,
                      help="explain what is going on")
    parser.add_option("-q", "--quality", default=0,
                      metavar="quality", help="choose what format to download based on bitrate / video resolution. "
                                              "it will download the best format by default")
    parser.add_option("-Q", "--flexible-quality", default=0,
                      metavar="amount", dest="flexibleq", help="allow given quality (as above) to differ by an amount")
    parser.add_option("--list-quality", dest="list_quality", action="store_true", default=False,
                      help="list the quality for a video")
    parser.add_option("-S", "--subtitle",
                      action="store_true", dest="subtitle", default=False,
                      help="download subtitle from the site if available")
    parser.add_option("-M", "--merge-subtitle", action="store_true", dest="merge_subtitle",
                      default=False, help="merge subtitle with video/audio file with corresponding ISO639-3 language code."
                                          "this invokes --remux automatically. use with -S for external also.")
    parser.add_option("--force-subtitle", dest="force_subtitle", default=False,
                      action="store_true", help="download only subtitle if its used with -S")
    parser.add_option("--require-subtitle", dest="require_subtitle", default=False,
                      action="store_true", help="download only if a subtitle is available")
    parser.add_option("--all-subtitles", dest="get_all_subtitles", default=False, action="store_true",
                      help="Download all available subtitles for the video")
    parser.add_option("--raw-subtitles", dest="get_raw_subtitles", default=False, action="store_true",
                      help="also download the subtitles in their native format")
    parser.add_option("--convert-subtitle-colors", dest="convert_subtitle_colors", default=False, action="store_true",
                      help="converts the color information in subtitles, to <font color=""> tags")
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
                      metavar="preferred", help="preferred download method (dash, hls, hds, http or rtmp)")
    parser.add_option("--exclude", dest="exclude", default=None,
                      metavar="WORD1,WORD2,...", help="exclude videos with the WORD(s) in the filename. comma separated.")
    parser.add_option("-g", "--get-url",
                      action="store_true", dest="get_url", default=False,
                      help="do not download any video, but instead print the URL.")
    parser.add_option("--dont-verify-ssl-cert", action="store_false", dest="ssl_verify", default=True,
                      help="Don't attempt to verify SSL certificates.")
    parser.add_option("--http-header", dest="http_headers", default=None, metavar="header1=value;header2=value2",
                      help="A header to add to each HTTP request.")
    parser.add_option("--stream-priority", dest="stream_prio", default=None, metavar="dash,hls,hds,http,rtmp",
                      help="If two streams have the same quality, choose the one you prefer")
    parser.add_option("--remux", dest="remux", default=False, action="store_true",
                      help="Remux from one container to mp4 using ffmpeg or avconv")
    parser.add_option("--include-clips", dest="include_clips", default=False, action="store_true",
                      help="include clips from websites when using -A")
    parser.add_option("--cmore-operatorlist", dest="cmoreoperatorlist", default=False, action="store_true",
                      help="show operatorlist for cmore")
    parser.add_option("--cmore-operator", dest="cmoreoperator", default=None, metavar="operator")
    parser.add_option("--proxy", dest="proxy", default=None,
                      metavar="proxy", help='Use the specified HTTP/HTTPS/SOCKS proxy. To enable experimental '
                                            'SOCKS proxy, specify a proper scheme. For example '
                                            'socks5://127.0.0.1:1080/.')

    (options, args) = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(0)
    if len(args) < 1:
        parser.error("Incorrect number of arguments")
    if options.exclude:
        options.exclude = options.exclude.split(",")
    if options.require_subtitle:
        if options.merge_subtitle:
            options.merge_subtitle = True
        else:
            options.subtitle = True
    if options.merge_subtitle:
        options.remux = True
    options = mergeParserOption(Options(), options)
    if options.silent_semi:
        options.silent = True
    setup_log(options.silent, options.verbose)

    if options.cmoreoperatorlist:
        c = Cmore(options, args)
        c.operatorlist()
        sys.exit(0)

    if options.proxy:
        options.proxy = options.proxy.replace("socks5", "socks5h", 1)
        options.proxy = dict(http=options.proxy,
                             https=options.proxy)

    if options.flexibleq and not options.quality:
        log.error("flexible-quality requires a quality")
        sys.exit(4)

    urls = args

    try:
        if len(urls) == 1:
            get_media(urls[0], options)
        else:
            get_multiple_media(urls, options)
    except KeyboardInterrupt:
        print("")


def mergeParserOption(options, parser):
    options.output = parser.output
    options.resume = parser.resume
    options.live = parser.live
    options.capture_time = parser.capture_time
    options.silent = parser.silent
    options.force = parser.force
    options.quality = parser.quality
    options.flexibleq = parser.flexibleq
    options.list_quality = parser.list_quality
    options.subtitle = parser.subtitle
    options.merge_subtitle = parser.merge_subtitle
    options.silent_semi = parser.silent_semi
    options.username = parser.username
    options.password = parser.password
    options.thumbnail = parser.thumbnail
    options.all_episodes = parser.all_episodes
    options.all_last = parser.all_last
    options.force_subtitle = parser.force_subtitle
    options.require_subtitle = parser.require_subtitle
    options.preferred = parser.preferred
    options.verbose = parser.verbose
    options.exclude = parser.exclude
    options.get_url = parser.get_url
    options.ssl_verify = parser.ssl_verify
    options.http_headers = parser.http_headers
    options.stream_prio = parser.stream_prio
    options.remux = parser.remux
    options.get_all_subtitles = parser.get_all_subtitles
    options.get_raw_subtitles = parser.get_raw_subtitles
    options.convert_subtitle_colors = parser.convert_subtitle_colors
    options.include_clips = parser.include_clips
    options.cmoreoperatorlist = parser.cmoreoperatorlist
    options.cmoreoperator = parser.cmoreoperator
    options.proxy = parser.proxy
    return options
