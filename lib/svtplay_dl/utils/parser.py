import argparse


def parser(version):
    parser = argparse.ArgumentParser(prog="svtplay-dl")
    general = parser.add_argument_group()

    general.add_argument('--version', action='version', version='%(prog)s {0}'.format(version))
    general.add_argument("-o", "--output", metavar="output", help="outputs to the given filename or folder")
    general.add_argument("-f", "--force", action="store_true", dest="force", default=False,
                         help="overwrite if file exists already")
    general.add_argument("-r", "--resume", action="store_true", dest="resume", default=False,
                         help="resume a download (RTMP based ones)")
    general.add_argument("-l", "--live", action="store_true", dest="live", default=False,
                         help="enable for live streams (RTMP based ones)")
    general.add_argument("-c", "--capture_time", default=-1, type=int, metavar="capture_time",
                         help="define capture time in minutes of a live stream")
    general.add_argument("-s", "--silent", action="store_true", dest="silent", default=False, help="be less verbose")
    general.add_argument("--silent-semi", action="store_true", dest="silent_semi", default=False,
                         help="only show a message when the file is downloaded")
    general.add_argument("-u", "--username", default=None, help="username")
    general.add_argument("-p", "--password", default=None, help="password")
    general.add_argument("-t", "--thumbnail", action="store_true", dest="thumbnail", default=False,
                         help="download thumbnail from the site if available")
    general.add_argument("-g", "--get-url", action="store_true", dest="get_url", default=False,
                         help="do not download any video, but instead print the URL.")
    general.add_argument("--dont-verify-ssl-cert", action="store_false", dest="ssl_verify", default=True,
                         help="Don't attempt to verify SSL certificates.")
    general.add_argument("--http-header", dest="http_headers", default=None, metavar="header1=value;header2=value2",
                         help="A header to add to each HTTP request.")
    general.add_argument("--remux", dest="remux", default=False, action="store_true",
                         help="Remux from one container to mp4 using ffmpeg or avconv")
    general.add_argument("--exclude", dest="exclude", default=None, metavar="WORD1,WORD2,...",
                         help="exclude videos with the WORD(s) in the filename. comma separated.")
    general.add_argument("--proxy", dest="proxy", default=None,
                         metavar="proxy", help="Use the specified HTTP/HTTPS/SOCKS proxy. To enable experimental "
                                               "SOCKS proxy, specify a proper scheme. For example "
                                               "socks5://127.0.0.1:1080/.")
    general.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False,
                         help="explain what is going on")

    quality = parser.add_argument_group("Quality")
    quality.add_argument("-q", "--quality", default=0, metavar="quality",
                         help="choose what format to download based on bitrate / video resolution."
                              "it will download the best format by default")
    quality.add_argument("-Q", "--flexible-quality", default=0, metavar="amount", dest="flexibleq",
                         help="allow given quality (as above) to differ by an amount")
    quality.add_argument("-P", "--preferred", default=None, metavar="preferred",
                         help="preferred download method (dash, hls, hds, http or rtmp)")
    quality.add_argument("--list-quality", dest="list_quality", action="store_true", default=False,
                         help="list the quality for a video")
    quality.add_argument("--stream-priority", dest="stream_prio", default=None, metavar="dash,hls,hds,http,rtmp",
                         help="If two streams have the same quality, choose the one you prefer")

    subtitle = parser.add_argument_group("Subtitle")
    subtitle.add_argument("-S", "--subtitle", action="store_true", dest="subtitle", default=False,
                          help="download subtitle from the site if available")
    subtitle.add_argument("-M", "--merge-subtitle", action="store_true", dest="merge_subtitle", default=False,
                          help="merge subtitle with video/audio file with corresponding ISO639-3 language code. this invokes --remux automatically. use with -S for external also.")
    subtitle.add_argument("--force-subtitle", dest="force_subtitle", default=False, action="store_true",
                          help="download only subtitle if its used with -S")
    subtitle.add_argument("--require-subtitle", dest="require_subtitle", default=False, action="store_true",
                          help="download only if a subtitle is available")
    subtitle.add_argument("--all-subtitles", dest="get_all_subtitles", default=False, action="store_true",
                          help="Download all available subtitles for the video")
    subtitle.add_argument("--raw-subtitles", dest="get_raw_subtitles", default=False, action="store_true",
                          help="also download the subtitles in their native format")
    subtitle.add_argument("--convert-subtitle-colors", dest="convert_subtitle_colors", default=False,
                          action="store_true",
                          help='converts the color information in subtitles, to <font color=""> tags')

    alleps = parser.add_argument_group("All")
    alleps.add_argument("-A", "--all-episodes", action="store_true", dest="all_episodes", default=False,
                        help="try to download all episodes")
    alleps.add_argument("--all-last", dest="all_last", default=-1, type=int, metavar="NN",
                        help="get last NN episodes instead of all episodes")
    alleps.add_argument("--include-clips", dest="include_clips", default=False, action="store_true",
                        help="include clips from websites when using -A")

    cmorep = parser.add_argument_group("C More")
    cmorep.add_argument("--cmore-operatorlist", dest="cmoreoperatorlist", default=False, action="store_true",
                        help="show operatorlist for cmore")
    cmorep.add_argument("--cmore-operator", dest="cmoreoperator", default=None, metavar="operator")

    parser.add_argument('urls', nargs="*")
    options = parser.parse_args()
    return parser, options


def mergeparseroption(options, parser):
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
