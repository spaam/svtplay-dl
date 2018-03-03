# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil: coding: utf-8 -*-
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8
from __future__ import absolute_import
import sys
import logging
import re
import unicodedata
import platform
from operator import itemgetter
import subprocess

try:
    import HTMLParser
except ImportError:
    # pylint: disable-msg=import-error
    import html.parser as HTMLParser
try:
    from requests import Session
    from requests.adapters import HTTPAdapter
    from requests.packages.urllib3.util.retry import Retry
except ImportError:
    print("You need to install python-requests to use this script")
    sys.exit(3)

from svtplay_dl import error

is_py2 = (sys.version_info[0] == 2)
is_py3 = (sys.version_info[0] == 3)
is_py2_old = (sys.version_info < (2, 7))

# Used for UA spoofing in get_http_data()
FIREFOX_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.3'

# TODO: should be set as the default option in the argument parsing?
DEFAULT_PROTOCOL_PRIO = ["dash", "hls", "hds", "http", "rtmp"]
LIVE_PROTOCOL_PRIO = ["hls", "dash", "hds", "http", "rtmp"]

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr

retry = Retry(
    total=5,
    read=5,
    connect=5,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504)
)


class HTTP(Session):
    def __init__(self, options, *args, **kwargs):
        Session.__init__(self, *args, **kwargs)
        adapter = HTTPAdapter(max_retries=retry)
        self.mount('http://', adapter)
        self.mount('https://', adapter)
        self.verify = options.ssl_verify
        self.proxy = options.proxy
        if options.http_headers:
            self.headers.update(self.split_header(options.http_headers))
        self.headers.update({"User-Agent": FIREFOX_UA})

    def check_redirect(self, url):
        return self.get(url, stream=True).url

    def request(self, method, url, *args, **kwargs):
        headers = kwargs.pop("headers", None)
        if headers:
            for i in headers.keys():
                self.headers[i] = headers[i]
        log.debug("HTTP getting %r", url)
        res = Session.request(self, method, url, verify=self.verify, proxies=self.proxy, *args, **kwargs)
        return res

    def split_header(self, headers):
        return dict(x.split('=') for x in headers.split(';'))


def sort_quality(data):
    data = sorted(data, key=lambda x: (x.bitrate, x.name()), reverse=True)
    datas = []
    for i in data:
        datas.append([i.bitrate, i.name()])
    return datas


def list_quality(videos):
    data = sort_quality(videos)
    log.info("Quality\tMethod")
    for i in data:
        log.info("%s\t%s", i[0], i[1].upper())


def protocol_prio(streams, priolist):
    """
    Given a list of VideoRetriever objects and a prioritized list of
    accepted protocols (as strings) (highest priority first), return
    a list of VideoRetriever objects that are accepted, and sorted
    by bitrate, and then protocol priority.
    """
    # Map score's to the reverse of the list's index values
    proto_score = dict(zip(priolist, range(len(priolist), 0, -1)))
    log.debug("Protocol priority scores (higher is better): %s", str(proto_score))

    # Build a tuple (bitrate, proto_score, stream), and use it
    # for sorting.
    prioritized = [(s.bitrate, proto_score[s.name()], s) for
                   s in streams if s.name() in proto_score]
    return [x[2] for x in sorted(prioritized, key=itemgetter(0, 1), reverse=True)]


def select_quality(options, streams):
    high = 0
    if isinstance(options.quality, str):
        try:
            quality = int(options.quality.split("-")[0])
            if len(options.quality.split("-")) > 1:
                high = int(options.quality.split("-")[1])
        except ValueError:
            raise error.UIException("Requested quality is invalid. use a number or range lowerNumber-higherNumber")
    else:
        quality = options.quality
    try:
        optq = int(quality)
    except ValueError:
        raise error.UIException("Requested quality needs to be a number")

    try:
        optf = int(options.flexibleq)
    except ValueError:
        raise error.UIException("Flexible-quality needs to be a number")

    if optf == 0 and high:
        optf = (high - quality) / 2
        optq = quality + (high - quality) / 2

    # Extract protocol prio, in the form of "hls,hds,http,rtmp",
    # we want it as a list

    if options.stream_prio:
        proto_prio = options.stream_prio.split(',')
    elif options.live or streams[0].options.live:
        proto_prio = LIVE_PROTOCOL_PRIO
    else:
        proto_prio = DEFAULT_PROTOCOL_PRIO

    # Filter away any unwanted protocols, and prioritize
    # based on --stream-priority.
    streams = protocol_prio(streams, proto_prio)

    if len(streams) == 0:
        raise error.NoRequestedProtocols(
            requested=proto_prio,
            found=list(set([s.name() for s in streams]))
        )

    # Build a dict indexed by bitrate, where each value
    # is the stream with the highest priority protocol.
    stream_hash = {}
    for s in streams:
        if s.bitrate not in stream_hash:
            stream_hash[s.bitrate] = s

    avail = sorted(stream_hash.keys(), reverse=True)

    # wanted_lim is a two element tuple defines lower/upper bounds
    # (inclusive). By default, we want only the best for you
    # (literally!).
    wanted_lim = (avail[0],) * 2
    if optq:
        wanted_lim = (optq - optf, optq + optf)

    # wanted is the filtered list of available streams, having
    # a bandwidth within the wanted_lim range.
    wanted = [a for a in avail if a >= wanted_lim[0] and a <= wanted_lim[1]]

    # If none remains, the bitrate filtering was too tight.
    if len(wanted) == 0:
        data = sort_quality(streams)
        quality = ", ".join("%s (%s)" % (str(x), str(y)) for x, y in data)
        raise error.UIException("Can't find that quality. Try one of: %s (or "
                                "try --flexible-quality)" % quality)

    http = HTTP(options)
    # Test if the wanted stream is available. If not try with the second best and so on.
    for w in wanted:
        res = http.get(stream_hash[w].url, cookies=stream_hash[w].kwargs["cookies"])
        if res is not None and res.status_code < 404:
            return stream_hash[w]

    raise error.UIException("Streams not available to download.")


def ensure_unicode(s):
    """
    Ensure string is a unicode string. If it isn't it assumed it is
    utf-8 and decodes it to a unicode string.
    """
    if (is_py2 and isinstance(s, str)) or (is_py3 and isinstance(s, bytes)):
        s = s.decode('utf-8', 'replace')
    return s


def decode_html_entities(s):
    """
    Replaces html entities with the character they represent.

        >>> print(decode_html_entities("&lt;3 &amp;"))
        <3 &
    """
    parser = HTMLParser.HTMLParser()

    def unesc(m):
        return parser.unescape(m.group())
    return re.sub(r'(&[^;]+;)', unesc, ensure_unicode(s))


def filenamify(title):
    """
    Convert a string to something suitable as a file name. E.g.

     Matlagning del 1 av 10 - Räksmörgås | SVT Play
       ->  matlagning.del.1.av.10.-.raksmorgas.svt.play
    """
    # ensure it is unicode
    title = ensure_unicode(title)

    # NFD decomposes chars into base char and diacritical mark, which
    # means that we will get base char when we strip out non-ascii.
    title = unicodedata.normalize('NFD', title)

    # Convert to lowercase
    # Drop any non ascii letters/digits
    # Drop any leading/trailing whitespace that may have appeared
    title = re.sub(r'[^a-z0-9 .-]', '', title.lower().strip())

    # Replace whitespace with dot
    title = re.sub(r'\s+', '.', title)
    title = re.sub(r'\.-\.', '-', title)

    return title


def download_thumbnail(options, url):
    data = Session.get(url).content

    filename = re.search(r"(.*)\.[a-z0-9]{2,3}$", options.output)
    tbn = "%s.tbn" % filename.group(1)
    log.info("Thumbnail: %s", tbn)

    fd = open(tbn, "wb")
    fd.write(data)
    fd.close()


def which(program):
    import os

    if platform.system() == "Windows":
        program = "{0}.exe".format(program)

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
        if os.path.isfile(program):
            exe_file = os.path.join(os.getcwd(), program)
            if is_exe(exe_file):
                return exe_file
    return None


def run_program(cmd, show=True):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stderr = stderr.decode('utf-8', 'replace')
    if p.returncode != 0 and show:
        msg = stderr.strip()
        log.error("Something went wrong: {0}".format(msg))
    return p.returncode, stdout, stderr
