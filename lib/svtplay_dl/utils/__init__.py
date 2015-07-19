# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
from __future__ import absolute_import
import sys
import socket
import logging
import re
import time
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
FIREFOX_UA = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3'

from svtplay_dl.utils.urllib import build_opener, Request, HTTPCookieProcessor, \
                                    HTTPRedirectHandler, HTTPError, \
                                    addinfourl, Cookie, CookieJar, SimpleCookie, urlparse, urlencode, httplib2

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr
h = httplib2.Http()

class NoRedirectHandler(HTTPRedirectHandler):
    def __init__(self):
        pass

    def http_error_302(self, req, fp, code, msg, headers):
        infourl = addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        infourl.code = code
        return infourl
    http_error_300 = http_error_302
    http_error_301 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302

def get_http_data(url, header=None, post=None, useragent=FIREFOX_UA, referer=None, cookiejar=None):
    error = None
    method = "GET"
    standard_headers = {'Referer': referer, 'User-Agent': useragent}
    request_headers = {}
    for key, value in [head for head in standard_headers.items() if head[1]]:
        request_headers[key] = value
    if header:
        for key, value in [head for head in header.items() if head[1]]:
            request_headers[key] = value

    body = ""
    if post:
        method = "POST"
        body = urlencode(post)

    if not cookiejar:
        cookiejar = CookieJar()
    cookie_header = []
    for cookie in cookiejar:
        cookie_header.append(cookie.name + "=\"" + cookie.value.replace('"', r'\"') + "\"")
    if len(cookie_header) > 0:
        request_headers["Cookie"] = "; ".join(cookie_header)

    if url.find("manifest.f4m") > 0:
        parse = urlparse(url)
        url = "%s://%s%s?%s&hdcore=3.3.0" % (parse.scheme, parse.netloc, parse.path, parse.query)

    log.debug("HTTP getting %r", url)
    starttime = time.time()

    (response_headers, content) = h.request(url, method, headers = request_headers, body = body)
    if "set-cookie" in response_headers:
        cookies = SimpleCookie()
        cookies.load(response_headers["set-cookie"])
        for key, c in cookies.items():
            expires = c['expires'] or None
            if expires:
                try:
                    expires = time.strptime(expires, "%a, %d %b %Y %H:%M:%S GMT")
                except ValueError:
                    log.debug("Failed to decode cookie expires field '%s' as a time" % expires)
                    expires = None
                    pass
            cookie = Cookie(version=int(c['version'] or '0'),
                            name=key,
                            value=c.value,
                            port=None,
                            port_specified=False,
                            domain=c['domain'] or '',
                            domain_specified=True if c['domain'] else False,
                            domain_initial_dot=True if (c['domain'] and c['domain'].startswith(".")) else False,
                            path=c['path'] or None,
                            path_specified=True if c['path'] else False,
                            secure=True if c['secure'] else False,
                            expires=expires,
                            discard=True,
                            comment=None,
                            comment_url=None,
                            rest={'HttpOnly': None}
                            )
            cookiejar.set_cookie(cookie)

    if is_py3:
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            pass

    spent_time = time.time() - starttime
    bps = 8 * len(content) / max(spent_time, 0.001)

    log.debug("HTTP got %d bytes from %r in %.2fs (= %dbps)",
              len(content), url, spent_time, bps)

    return error, content

def get_http_data_old(url, header=None, post=None, useragent=FIREFOX_UA,
                  referer=None, cookiejar=None):
    """ Get the page to parse it for streams """
    if not cookiejar:
        cookiejar = CookieJar()

    if url.find("manifest.f4m") > 0:
        parse = urlparse(url)
        url = "%s://%s%s?%s&hdcore=3.3.0" % (parse.scheme, parse.netloc, parse.path, parse.query)

    log.debug("HTTP getting %r", url)
    starttime = time.time()
    error = None
    if post:
        if is_py3:
            post = bytes(post, encoding="utf-8")
        request = Request(url, data=post)
    else:
        request = Request(url)
    standard_header = {'Referer': referer, 'User-Agent': useragent}
    for key, value in [head for head in standard_header.items() if head[1]]:
        request.add_header(key, value)
    if header:
        for key, value in [head for head in header.items() if head[1]]:
            request.add_header(key, value)

    opener = build_opener(HTTPCookieProcessor(cookiejar))

    try:
        response = opener.open(request)
    except HTTPError as e:
        error = True
        data = e.read()
        return error, data

    if is_py3:
        data = response.read()
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
    else:
        try:
            data = response.read()
        except socket.error as e:
            return True, "Lost the connection to the server"
    response.close()

    spent_time = time.time() - starttime
    bps = 8 * len(data) / max(spent_time, 0.001)

    log.debug("HTTP got %d bytes from %r in %.2fs (= %dbps)",
              len(data), url, spent_time, bps)

    return error, data

def check_redirect(url):
    opener = build_opener(NoRedirectHandler())
    opener.addheaders += [('User-Agent', FIREFOX_UA)]
    response = opener.open(url)
    if response.code in (300, 301, 302, 303, 307):
        return response.headers["location"]
    else:
        return url

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
    for i in streams:
        if int(i.bitrate) == selected:
            stream = i
    return stream

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
    Convert a string to something suitable as a file name.

        >>> print(filenamify(u'Matlagning del 1 av 10 - R\xe4ksm\xf6rg\xe5s | SVT Play'))
        matlagning-del-1-av-10-raksmorgas-svt-play

    """
    # ensure it is unicode
    title = ensure_unicode(title)

    # NFD decomposes chars into base char and diacritical mark, which means that we will get base char when we strip out non-ascii.
    title = unicodedata.normalize('NFD', title)

    # Drop any non ascii letters/digits
    title = re.sub(r'[^a-zA-Z0-9 -.]', '', title)
    # Drop any leading/trailing whitespace that may have appeared
    title = title.strip()
    # Lowercase
    title = title.lower()
    # Replace whitespace with dash
    title = re.sub(r'[-\s]+', '-', title)

    return title

def download_thumbnail(options, url):
    error, data = get_http_data(url)

    filename = re.search(r"(.*)\.[a-z0-9]{2,3}$", options.output)
    tbn = "%s.tbn" % filename.group(1)
    log.info("Thumbnail: %s", tbn)

    fd = open(tbn, "wb")
    fd.write(data)
    fd.close()
