import copy
import logging
import os
import sys
from datetime import datetime
from shutil import which

from svtplay_dl.error import UIException
from svtplay_dl.fetcher import VideoRetriever
from svtplay_dl.postprocess import postprocess
from svtplay_dl.service import Generic
from svtplay_dl.service import service_handler
from svtplay_dl.service.services import Raw
from svtplay_dl.service.services import sites
from svtplay_dl.subtitle import subtitle
from svtplay_dl.utils.nfo import write_nfo_episode
from svtplay_dl.utils.nfo import write_nfo_tvshow
from svtplay_dl.utils.output import filename
from svtplay_dl.utils.output import find_dupes
from svtplay_dl.utils.output import formatname
from svtplay_dl.utils.stream import list_quality
from svtplay_dl.utils.stream import select_quality
from svtplay_dl.utils.stream import subtitle_decider
from svtplay_dl.utils.text import exclude


def get_multiple_media(urls, config):
    if config.get("output") and os.path.isfile(config.get("output")):
        logging.error("Output must be a directory if used with multiple URLs")
        sys.exit(2)
    elif config.get("output") and not os.path.exists(config.get("output")):
        try:
            os.makedirs(config.get("output"))
        except OSError as e:
            logging.error("%s: %s", e.strerror, e.filename)
            return

    for url in urls:
        get_media(url, copy.copy(config))


def get_media(url, options, version="Unknown"):
    if "http" not in url[:4]:
        url = f"http://{url}"

    if options.get("verbose"):
        logging.debug("version: %s", version)

    stream = service_handler(sites, options, url)
    if not stream:
        generic = Generic(options, url)
        url, stream = generic.get(sites)
    if not stream:
        if url.find(".f4m") > 0 or url.find(".m3u8") > 0 or url.find(".mpd") > 1:
            stream = Raw(options, url)
        if not stream:
            logging.error("That site is not supported. Make a ticket or send a message")
            sys.exit(2)

    if options.get("all_episodes") or stream.config.get("all_episodes"):
        get_all_episodes(stream, url, options)
    else:
        get_one_media(stream)


def get_all_episodes(stream, url, options):
    name = os.path.dirname(formatname({"basedir": True}, stream.config))

    if name and os.path.isfile(name):
        logging.error("Output must be a directory if used with --all-episodes")
        sys.exit(2)
    elif name and not os.path.exists(name):
        try:
            os.makedirs(name)
        except OSError as e:
            logging.error("%s: %s", e.strerror, e.filename)
            return

    episodes = stream.find_all_episodes(stream.config)
    if episodes is None:
        return
    for idx, o in enumerate(episodes):
        if o == url:
            substream = stream
        else:
            substream = service_handler(sites, copy.copy(stream.config), o)

        logging.info("Episode %d of %d", idx + 1, len(episodes))
        logging.info("Url: %s", o)

        if not (options.get("get_url") and options.get("get_only_episode_url")):
            # get_one_media overwrites options.output...
            get_one_media(substream)


def get_one_media(stream):
    # Make an automagic filename
    if not filename(stream):
        return

    if stream.config.get("merge_subtitle"):
        if not which("ffmpeg"):
            logging.error("--merge-subtitle needs ffmpeg. Please install ffmpeg.")
            logging.info("https://ffmpeg.org/download.html")
            sys.exit(2)

    videos = []
    subtitles = []
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
                    subtitles.append(i)
    except Exception:
        if stream.config.get("verbose"):
            raise
        else:
            logging.error("svtplay-dl crashed")
            logging.error("Run again and add --verbose as an argument, to get more information")
            logging.error("If the error persists, you can report it at https://github.com/spaam/svtplay-dl/issues")
            logging.error("Include the URL used, the stack trace and the output of svtplay-dl --version in the issue")
        return

    try:
        after_date = datetime.strptime(stream.config.get("after_date"), "%Y-%m-%d")
    except (ValueError, TypeError, KeyError, AttributeError):  # gotta catch em all..
        after_date = None
    try:
        pub_date = datetime.fromtimestamp(stream.output["publishing_datetime"])
    except (ValueError, TypeError, KeyError):
        pub_date = None
    if after_date is not None and pub_date is not None and pub_date.date() < after_date.date():
        logging.info(
            "Video %sS%dE%d skipped since published %s.",
            stream.output["title"],
            stream.output["season"],
            stream.output["episode"],
            pub_date.date(),
        )
        return

    if stream.config.get("require_subtitle") and not subtitles:
        logging.info("No subtitles available")
        return

    if not stream.config.get("list_quality"):
        subtitle_decider(stream, subtitles)
        if stream.config.get("force_subtitle"):
            return

    if not videos:
        errormsg = None
        for exc in error:
            if errormsg:
                errormsg = f"{errormsg}. {str(exc)}"
            else:
                errormsg = str(exc)
        if errormsg:
            logging.error("No videos found. %s", errormsg)
        else:
            logging.error("No videos found.")
    else:
        if stream.config.get("list_quality"):
            list_quality(videos)
            return
        if stream.config.get("nfo"):
            # Create NFO files
            write_nfo_episode(stream.output, stream.config)
            write_nfo_tvshow(stream.output, stream.config)
            if stream.config.get("force_nfo"):
                return
        try:
            fstream = select_quality(stream.config, videos)
        except UIException as e:
            logging.error(e)
            return

        if fstream.config.get("get_url"):
            print(fstream.url)
            return

        dupe, fileame = find_dupes(fstream.output, stream.config)
        if dupe and not stream.config.get("force"):
            logging.warning("File (%s) already exists. Use --force to overwrite", fileame.name)
            return
        if fstream.config.get("output_format") and fstream.config.get("output_format").lower() not in ["mkv", "mp4"]:
            logging.error("Unknown output format. please choose mp4 or mkv")
            sys.exit(2)
        try:
            logging.info("Selected to download %s, bitrate: %s format: %s", fstream.name, fstream.bitrate, fstream.format)
            fstream.download()
        except UIException as e:
            if fstream.config.get("verbose"):
                raise e
            logging.error(e)
            sys.exit(2)

        if fstream.config.get("thumbnail") and hasattr(stream, "get_thumbnail"):
            stream.get_thumbnail(stream.config)

        if fstream.config.get("silent_semi") and fstream.finished:
            logging.log(25, "Download of %s was completed", formatname(fstream.output, fstream.config))

        if fstream.config.get("no_postprocess") is True or all(fstream.config.get(x) for x in ["no_remux", "no_merge"]) is True:
            logging.info("All done. Not postprocessing files, leaving them completely untouched.")
            return

        post = postprocess(fstream, fstream.config, subtitles)
        if fstream.audio and not post.detect and fstream.finished:
            logging.warning("Can't find ffmpeg/avconv. audio and video is in seperate files. if you dont want this use -P hls or hds")
        if post.detect and fstream.config.get("no_merge") is False:
            post.merge()
        else:
            logging.info("All done. Not postprocessing files, leaving them completely untouched.")
