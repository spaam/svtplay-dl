# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil: coding: utf-8 -*-
# ex:ts=4:sw=4:sts=4:et:fenc=utf-8
from __future__ import absolute_import
import sys
import logging
import re
import unicodedata

try:
    import HTMLParser
except ImportError:
    # pylint: disable-msg=import-error
    import html.parser as HTMLParser

is_py2 = (sys.version_info[0] == 2)
is_py3 = (sys.version_info[0] == 3)
is_py2_old = (sys.version_info < (2, 7))

# Used for UA spoofing in get_http_data()
FIREFOX_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.3'

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr

try:
    from requests import Session
except ImportError:
    print("You need to install python-requests to use this script")
    sys.exit(3)


class HTTP(Session):
    def __init__(self, options, *args, **kwargs):
        Session.__init__(self, *args, **kwargs)
        self.verify = options.ssl_verify
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
        res = Session.request(self, method, url, verify=self.verify, *args, **kwargs)
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
        log.info("%s\t%s" % (i[0], i[1].upper()))


def prio_streams(options, streams, selected):
    prio = options.stream_prio
    if prio is None:
        prio = ["hls","hds", "http", "rtmp"]
    if isinstance(prio, str):
        prio = prio.split(",")
    lstreams = []
    for i in streams:
        if int(i.bitrate) == selected:
            lstreams.append(i)
    return [x for (y, x) in sorted(zip(prio, lstreams))]


def select_quality(options, streams):
    available = sorted(int(x.bitrate) for x in streams)
    try:
        optq = int(options.quality)
    except ValueError:
        log.error("Requested quality need to be a number")
        sys.exit(4)
    if optq:
        try:
            optf = int(options.flexibleq)
        except ValueError:
            log.error("Flexible-quality need to be a number")
            sys.exit(4)
        if not optf:
            wanted = [optq]
        else:
            wanted = range(optq-optf, optq+optf+1)
    else:
        wanted = [available[-1]]

    selected = None
    for q in available:
        if q in wanted:
            selected = q
            break
    if not selected and selected != 0:
        data = sort_quality(streams)
        quality = ", ".join("%s (%s)" % (str(x), str(y)) for x, y in data)
        log.error("Can't find that quality. Try one of: %s (or try --flexible-quality)", quality)

        sys.exit(4)
    return prio_streams(options, streams, selected)[0]


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

    return title


def download_thumbnail(options, url):
    data = Session.get(url).content

    filename = re.search(r"(.*)\.[a-z0-9]{2,3}$", options.output)
    tbn = "%s.tbn" % filename.group(1)
    log.info("Thumbnail: %s", tbn)

    fd = open(tbn, "wb")
    fd.write(data)
    fd.close()
