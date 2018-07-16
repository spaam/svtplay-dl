import os
import sys
import copy
import logging
from shutil import which


from svtplay_dl.log import log
from svtplay_dl.service import service_handler, Generic
from svtplay_dl.service.services import sites, Raw
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.output import filename, formatname
from svtplay_dl.postprocess import postprocess
from svtplay_dl.utils.stream import select_quality, list_quality
from svtplay_dl.utils.text import exclude
from svtplay_dl.error import UIException


def get_multiple_media(urls, config):
    if config.get("output") and os.path.isfile(config.output):
        log.error("Output must be a directory if used with multiple URLs")
        sys.exit(2)
    elif config.get("output") and not os.path.exists(config.get("output")):
        try:
            os.makedirs(config.get("output"))
        except OSError as e:
            log.error("%s: %s", e.strerror, e.filename)
            return

    for url in urls:
        get_media(url, copy.copy(config))


def get_media(url, options, version="Unknown"):
    if "http" not in url[:4]:
        url = "http://%s" % url

    if options.get("verbose"):
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

    if options.get("all_episodes"):
        get_all_episodes(stream, url)
    else:
        get_one_media(stream)


def get_all_episodes(stream, url):
    name = os.path.dirname(formatname(dict(), stream.config))

    if name and os.path.isfile(name):
        log.error("Output must be a directory if used with --all-episodes")
        sys.exit(2)
    elif name and not os.path.exists(name):
        try:
            os.makedirs(name)
        except OSError as e:
            log.error("%s: %s", e.strerror, e.filename)
            return

    episodes = stream.find_all_episodes(stream.config)
    if episodes is None:
        return
    for idx, o in enumerate(episodes):
        if o == url:
            substream = stream
        else:
            substream = service_handler(sites, copy.copy(stream.config), o)

        log.info("Episode %d of %d", idx + 1, len(episodes))
        log.info("Url: %s", o)

        # get_one_media overwrites options.output...
        get_one_media(substream)


def get_one_media(stream):
    # Make an automagic filename
    if not filename(stream):
        return

    if stream.config.get("merge_subtitle"):
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
            if isinstance(i, Exception):
                error.append(i)
            elif not exclude(stream.config, formatname(i.output, stream.config)):
                if isinstance(i, VideoRetriever):
                    if stream.config.get("preferred"):
                        if stream.config.get("preferred").lower() == i.name:
                            videos.append(i)
                    else:
                        videos.append(i)
                if isinstance(i, subtitle):
                    subs.append(i)
    except Exception as e:
        if stream.config.get("verbose"):
            raise
        else:
            logging.error("svtplay-dl crashed")
            logging.error("Run again and add --verbose as an argument, to get more information")
            logging.error("If the error persists, you can report it at https://github.com/spaam/svtplay-dl/issues")
            logging.error("Include the URL used, the stack trace and the output of svtplay-dl --version in the issue")
        return

    if stream.config.get("require_subtitle") and not subs:
        logging.info("No subtitles available")
        return

    if stream.config.get("subtitle") and stream.config.get("get_url"):
        if subs:
            if stream.config.get("get_all_subtitles"):
                for sub in subs:
                    print(sub.url)
            else:
                print(subs[0].url)
        if stream.config.get("force_subtitle"):
            return

    def options_subs_dl(subfixes):
        if subs:
            if stream.config.get("get_all_subtitles"):
                for sub in subs:
                    sub.download()
                    if stream.config.get("merge_subtitle"):
                        if sub.subfix:
                            subfixes += [sub.subfix]
                        else:
                            stream.config.set("get_all_subtitles", False)
            else:
                subs[0].download()
        elif stream.config.get("merge_subtitle"):
            stream.config.set("merge_subtitle", False)

    if stream.config.get("subtitle") and not stream.config.get("get_url"):
        options_subs_dl(subfixes)
        if stream.config.get("force_subtitle"):
            return

    if stream.config.get("merge_subtitle") and not stream.config.get("subtitle"):
        options_subs_dl(subfixes)

    if not videos:
        errormsg = None
        for exc in error:
            if errormsg:
                errormsg = "{}. {}".format(errormsg, str(exc))
            else:
                errormsg = str(exc)
        logging.error("No videos found. {}".format(errormsg))
    else:
        if stream.config.get("list_quality"):
            list_quality(videos)
            return
        try:
            stream = select_quality(stream.config, videos)
            if stream.config.get("get_url"):
                print(stream.url)
                return
            logging.info("Selected to download %s, bitrate: %s", stream.name, stream.bitrate)
            stream.download()
        except UIException as e:
            if stream.config.get("verbose"):
                raise e
            log.error(e)
            sys.exit(2)

        if stream.config.get("thumbnail") and hasattr(stream, "get_thumbnail"):
            stream.get_thumbnail(stream.config)
        post = postprocess(stream, stream.config, subfixes)
        if stream.audio and post.detect:
            post.merge()
        if stream.audio and not post.detect and stream.finished:
            logging.warning("Cant find ffmpeg/avconv. audio and video is in seperate files. if you dont want this use -P hls or hds")
        if stream.name == "hls" or stream.config.get("remux"):
            post.remux()
        if stream.config.get("silent_semi") and stream.finished:
            logging.log(25, "Download of %s was completed" % stream.options.output)
