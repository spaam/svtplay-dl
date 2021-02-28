import argparse
import logging
import os
import platform

from yaml import safe_load

configdata = None

if platform.system() == "Windows":
    APPDATA = os.environ["APPDATA"]
    CONFIGFILE = os.path.join(APPDATA, "svtplay-dl", "svtplay-dl.yaml")
else:
    CONFIGFILE = os.path.expanduser("~/.svtplay-dl.yaml")


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
        self.default = {}

    def set(self, key, value):
        self.default[key] = value

    def get(self, key):
        if key in self.default:
            return self.default[key]

    def get_variable(self):
        return self.default

    def set_variable(self, value):
        self.default = value


def gen_parser(version="unknown"):
    parser = argparse.ArgumentParser(prog="svtplay-dl")
    general = parser.add_argument_group()

    general.add_argument("--version", action="version", version=f"%(prog)s {version}")
    general.add_argument("-o", "--output", metavar="output", default=None, help="outputs to the given filename or folder")
    general.add_argument(
        "--subfolder",
        action="store_true",
        default=False,
        help="Create a subfolder titled as the show, non-series gets in folder movies",
    )
    general.add_argument("--config", dest="configfile", metavar="configfile", default=CONFIGFILE, help="Specify configuration file")
    general.add_argument("-f", "--force", action="store_true", dest="force", default=False, help="overwrite if file exists already")
    general.add_argument("-r", "--resume", action="store_true", dest="resume", default=False, help="resume a download (RTMP obsolete)")
    general.add_argument("-l", "--live", action="store_true", dest="live", default=False, help="enable for live streams (RTMP based ones)")
    general.add_argument("-c", "--capture_time", default=-1, type=int, metavar="capture_time", help="define capture time in minutes of a live stream")
    general.add_argument("-s", "--silent", action="store_true", dest="silent", default=False, help="be less verbose")
    general.add_argument(
        "--silent-semi",
        action="store_true",
        dest="silent_semi",
        default=False,
        help="only show a message when the file is downloaded",
    )
    general.add_argument("-u", "--username", default=None, help="username")
    general.add_argument("-p", "--password", default=None, help="password")
    general.add_argument(
        "-t",
        "--thumbnail",
        action="store_true",
        dest="thumbnail",
        default=False,
        help="download thumbnail from the site if available",
    )
    general.add_argument(
        "-g",
        "--get-url",
        action="store_true",
        dest="get_url",
        default=False,
        help="do not download any video, but instead print the URL.",
    )
    general.add_argument(
        "--get-only-episode-url",
        action="store_true",
        dest="get_only_episode_url",
        default=False,
        help="do not get video URLs, only print the episode URL.",
    )
    general.add_argument(
        "--dont-verify-ssl-cert",
        action="store_false",
        dest="ssl_verify",
        default=True,
        help="Don't attempt to verify SSL certificates.",
    )
    general.add_argument(
        "--http-header",
        dest="http_headers",
        default=None,
        metavar="header1=value;header2=value2",
        help="A header to add to each HTTP request.",
    )
    general.add_argument(
        "--cookies",
        dest="cookies",
        default=None,
        metavar="cookie1=value;cookie2=value2",
        help="A cookies to add to each HTTP request.",
    )
    general.add_argument("--remux", dest="remux", default=False, action="store_true", help="Remux from one container to mp4 using ffmpeg or avconv")
    general.add_argument(
        "--exclude",
        dest="exclude",
        default=None,
        metavar="WORD1,WORD2,...",
        help="exclude videos with the WORD(s) in the filename. comma separated.",
    )
    general.add_argument("--after-date", dest="after_date", default=None, metavar="yyyy-MM-dd", help="only videos published on or after this date")
    general.add_argument(
        "--proxy",
        dest="proxy",
        default=None,
        metavar="proxy",
        help="Use the specified HTTP/HTTPS/SOCKS proxy. To enable experimental "
        "SOCKS proxy, specify a proper scheme. For example "
        "socks5://127.0.0.1:1080/.",
    )
    general.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="explain what is going on")
    general.add_argument("--nfo", action="store_true", dest="nfo", default=False, help="create a NFO file")
    general.add_argument("--force-nfo", action="store_true", dest="force_nfo", default=False, help="download only NFO if used with --nfo")
    general.add_argument(
        "--only-audio",
        action="store_true",
        dest="only_audio",
        default=False,
        help="only download audio if audio and video is seperated",
    )
    general.add_argument(
        "--only-video",
        action="store_true",
        dest="only_video",
        default=False,
        help="only download video if audio and video is seperated",
    )

    quality = parser.add_argument_group("Quality")
    quality.add_argument(
        "-q",
        "--quality",
        default=0,
        metavar="quality",
        help="choose what format to download based on bitrate / video resolution." "it will download the best format by default",
    )
    quality.add_argument(
        "-Q",
        "--flexible-quality",
        default=0,
        metavar="amount",
        dest="flexibleq",
        help="allow given quality (as above) to differ by an amount",
    )
    quality.add_argument("-P", "--preferred", default=None, metavar="preferred", help="preferred download method (dash, hls, hds, or http)")
    quality.add_argument("--list-quality", dest="list_quality", action="store_true", default=False, help="list the quality for a video")
    quality.add_argument(
        "--stream-priority",
        dest="stream_prio",
        default=None,
        metavar="dash,hls,hds,http",
        help="If two streams have the same quality, choose the one you prefer",
    )
    quality.add_argument(
        "--format-preferred",
        dest="format_preferred",
        default=None,
        metavar="h264,h264-51",
        help="Choose the format you prefer, --list-quality to show which one to choose from",
    )

    subtitle = parser.add_argument_group("Subtitle")
    subtitle.add_argument(
        "-S",
        "--subtitle",
        action="store_true",
        dest="subtitle",
        default=False,
        help="download subtitle from the site if available",
    )
    subtitle.add_argument(
        "-M",
        "--merge-subtitle",
        action="store_true",
        dest="merge_subtitle",
        default=False,
        help="merge subtitle with video/audio file with corresponding ISO639-3 language code." "this invokes --remux automatically.",
    )
    subtitle.add_argument(
        "--force-subtitle",
        dest="force_subtitle",
        default=False,
        action="store_true",
        help="download only subtitle if its used with -S",
    )
    subtitle.add_argument(
        "--require-subtitle",
        dest="require_subtitle",
        default=False,
        action="store_true",
        help="download only if a subtitle is available",
    )
    subtitle.add_argument(
        "--all-subtitles",
        dest="get_all_subtitles",
        default=False,
        action="store_true",
        help="Download all available subtitles for the video",
    )
    subtitle.add_argument(
        "--raw-subtitles",
        dest="get_raw_subtitles",
        default=False,
        action="store_true",
        help="also download the subtitles in their native format",
    )
    subtitle.add_argument(
        "--convert-subtitle-colors",
        dest="convert_subtitle_colors",
        default=False,
        action="store_true",
        help='converts the color information in subtitles, to <font color=""> tags',
    )

    alleps = parser.add_argument_group("All")
    alleps.add_argument("-A", "--all-episodes", action="store_true", dest="all_episodes", default=False, help="try to download all episodes")
    alleps.add_argument("--all-last", dest="all_last", default=-1, type=int, metavar="NN", help="get last NN episodes instead of all episodes")
    alleps.add_argument("--include-clips", dest="include_clips", default=False, action="store_true", help="include clips from websites when using -A")

    cmorep = parser.add_argument_group("C More")
    cmorep.add_argument("--cmore-operatorlist", dest="cmoreoperatorlist", default=False, action="store_true", help="show operatorlist for cmore")
    cmorep.add_argument("--cmore-operator", dest="cmoreoperator", default=None, metavar="operator")

    parser.add_argument("urls", nargs="*")

    return parser


def parser(version):
    parser = gen_parser(version)
    options = parser.parse_args()
    return parser, options


def setup_defaults():
    options = Options()
    options.set("output", None)
    options.set("subfolder", False)
    options.set("configfile", CONFIGFILE)
    options.set("resume", False)
    options.set("live", False)
    options.set("capture_time", -1)
    options.set("silent", False)
    options.set("force", False)
    options.set("quality", 0)
    options.set("flexibleq", 0)
    options.set("list_quality", False)
    options.set("other", None)
    options.set("subtitle", False)
    options.set("username", None)
    options.set("password", None)
    options.set("thumbnail", False)
    options.set("all_episodes", False)
    options.set("all_last", -1)
    options.set("merge_subtitle", False)
    options.set("force_subtitle", False)
    options.set("require_subtitle", False)
    options.set("get_all_subtitles", False)
    options.set("get_raw_subtitles", False)
    options.set("convert_subtitle_colors", False)
    options.set("preferred", None)
    options.set("verbose", False)
    options.set("nfo", False)
    options.set("force_nfo", False)
    options.set("output_auto", False)
    options.set("service", None)
    options.set("cookies", None)
    options.set("exclude", None)
    options.set("after_date", None)
    options.set("get_url", False)
    options.set("get_only_episode_url", False)
    options.set("ssl_verify", True)
    options.set("http_headers", None)
    options.set("format_preferred", None)
    options.set("stream_prio", None)
    options.set("remux", False)
    options.set("silent_semi", False)
    options.set("proxy", None)
    options.set("include_clips", False)
    options.set("cmoreoperatorlist", False)
    options.set("filename", "{title}.s{season}e{episode}.{episodename}-{id}-{service}.{ext}")
    options.set("only_audio", False)
    options.set("only_video", False)
    return _special_settings(options)


def parsertoconfig(config, parser):
    config.set("output", parser.output)
    config.set("subfolder", parser.subfolder)
    config.set("configfile", parser.configfile)
    config.set("resume", parser.resume)
    config.set("live", parser.live)
    config.set("capture_time", parser.capture_time)
    config.set("silent", parser.silent)
    config.set("force", parser.force)
    config.set("quality", parser.quality)
    config.set("flexibleq", parser.flexibleq)
    config.set("list_quality", parser.list_quality)
    config.set("subtitle", parser.subtitle)
    config.set("merge_subtitle", parser.merge_subtitle)
    config.set("silent_semi", parser.silent_semi)
    config.set("username", parser.username)
    config.set("password", parser.password)
    config.set("thumbnail", parser.thumbnail)
    config.set("all_episodes", parser.all_episodes)
    config.set("all_last", parser.all_last)
    config.set("force_subtitle", parser.force_subtitle)
    config.set("require_subtitle", parser.require_subtitle)
    config.set("preferred", parser.preferred)
    config.set("verbose", parser.verbose)
    config.set("nfo", parser.nfo)
    config.set("force_nfo", parser.force_nfo)
    config.set("exclude", parser.exclude)
    config.set("after_date", parser.after_date)
    config.set("get_url", parser.get_url)
    config.set("get_only_episode_url", parser.get_only_episode_url)
    config.set("ssl_verify", parser.ssl_verify)
    config.set("http_headers", parser.http_headers)
    config.set("cookies", parser.cookies)
    config.set("format_preferred", parser.format_preferred)
    config.set("stream_prio", parser.stream_prio)
    config.set("remux", parser.remux)
    config.set("get_all_subtitles", parser.get_all_subtitles)
    config.set("get_raw_subtitles", parser.get_raw_subtitles)
    config.set("convert_subtitle_colors", parser.convert_subtitle_colors)
    config.set("include_clips", parser.include_clips)
    config.set("cmoreoperatorlist", parser.cmoreoperatorlist)
    config.set("cmoreoperator", parser.cmoreoperator)
    config.set("proxy", parser.proxy)
    config.set("only_audio", parser.only_audio)
    config.set("only_video", parser.only_video)
    return _special_settings(config)


def _special_settings(config):
    if config.get("require_subtitle"):
        if config.get("merge_subtitle"):
            config.set("merge_subtitle", True)
        else:
            config.set("subtitle", True)
    if config.get("merge_subtitle"):
        config.set("remux", True)
        config.set("subtitle", True)

    if config.get("silent_semi"):
        config.set("silent", True)

    if config.get("proxy"):
        config.set("proxy", config.get("proxy").replace("socks5", "socks5h", 1))
        config.set("proxy", dict(http=config.get("proxy"), https=config.get("proxy")))

    if config.get("get_only_episode_url"):
        config.set("get_url", True)

    return config


def merge(old, new):
    if isinstance(new, list):
        new = {list(i.keys())[0]: i[list(i.keys())[0]] for i in new}
    config = setup_defaults()
    if new:
        for item in new:
            if item in new:
                if new[item] != config.get(item):  # Check if new value is not a default one.
                    old[item] = new[item]
            else:
                old[item] = new[item]
    options = Options()
    options.set_variable(old)
    return options


def readconfig(config, configfile, service=None, preset=None):
    global configdata

    if configfile and configdata is None:
        try:
            with open(configfile) as fd:
                data = fd.read()
                configdata = safe_load(data)
        except PermissionError:
            logging.error(f"Permission denied while reading config: {configfile}")

    if configdata is None:
        return config

    if "default" in configdata:
        config = merge(config.get_variable(), configdata["default"])

    if service and "service" in configdata and service in configdata["service"]:
        config = merge(config.get_variable(), configdata["service"][service])

    if preset and "presets" in configdata and preset in configdata["presets"]:
        config = merge(config.get_variable(), configdata["presets"][preset])

    return config
