import os
import sys
import copy


from svtplay_dl.log import log
from svtplay_dl.service import service_handler, Generic
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.output import filename
from svtplay_dl.postprocess import postprocess
from svtplay_dl.utils import select_quality, list_quality
from svtplay_dl.error import UIException


from svtplay_dl.service.aftonbladet import Aftonbladet, Aftonbladettv
from svtplay_dl.service.bambuser import Bambuser
from svtplay_dl.service.bigbrother import Bigbrother
from svtplay_dl.service.cmore import Cmore
from svtplay_dl.service.dbtv import Dbtv
from svtplay_dl.service.disney import Disney
from svtplay_dl.service.dplay import Dplay
from svtplay_dl.service.dr import Dr
from svtplay_dl.service.efn import Efn
from svtplay_dl.service.expressen import Expressen
from svtplay_dl.service.facebook import Facebook
from svtplay_dl.service.filmarkivet import Filmarkivet
from svtplay_dl.service.flowonline import Flowonline
from svtplay_dl.service.hbo import Hbo
from svtplay_dl.service.twitch import Twitch
from svtplay_dl.service.lemonwhale import Lemonwhale
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
from svtplay_dl.service.vidme import Vidme
from svtplay_dl.service.vimeo import Vimeo
from svtplay_dl.service.youplay import Youplay

sites = [
    Aftonbladet,
    Aftonbladettv,
    Bambuser,
    Barnkanalen,
    Bigbrother,
    Cmore,
    Dbtv,
    Disney,
    Dplay,
    Dr,
    Efn,
    Expressen,
    Facebook,
    Filmarkivet,
    Flowonline,
    Hbo,
    Twitch,
    Lemonwhale,
    Mtvservices,
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
    Vidme,
    Vimeo,
    Vg,
    Youplay,
    Riksdagen,
    Raw]


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


def get_media(url, options, version="Unknown"):
    if "http" not in url[:4]:
        url = "http://%s" % url

    if options.silent_semi:
        options.silent = True
    if options.verbose:
        log.debug("version: {0}".format(version))
    stream = service_handler(sites, options, url)
    if not stream:
        generic = Generic(options, url)
        url, stream = generic.get(sites)
    if not stream:
        if url.find(".f4m") > 0 or url.find(".m3u8") > 0:
            stream = Raw(options, url)
        if not stream:
            log.error("That site is not supported. Make a ticket or send a message")
            sys.exit(2)

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
        log.info("Url: %s",o)

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

    if options.subtitle and not options.get_url:
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
            stream.get_thumbnail(options)
        post = postprocess(stream, options, subfixes)
        if stream.name() == "dash" and post.detect:
            post.merge()
        if stream.name() == "dash" and not post.detect and stream.finished:
            log.warning("Cant find ffmpeg/avconv. audio and video is in seperate files. if you dont want this use -P hls or hds")
        if options.remux:
            post.remux()
        if options.silent_semi and stream.finished:
            log.log(25, "Download of %s was completed" % stream.options.output)
