from __future__ import absolute_import
import sys
import logging

if sys.version_info > (3, 0):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlparse, parse_qs, unquote_plus, quote_plus
    from io import BytesIO as StringIO
else:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urlparse import urlparse, parse_qs
    from urllib import unquote_plus, quote_plus
    from StringIO import StringIO

log = logging.getLogger('svtplay_dl')
progress_stream = sys.stderr

def get_http_data(url, method="GET", header="", data=""):
    """ Get the page to parse it for streams """
    request = Request(url)
    request.add_header('User-Agent', 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-GB; rv:1.9.0.3) Gecko/2008092417 Firefox/3.0.3')

    if len(header) > 0:
        request.add_header('Content-Type', header)
    if len(data) > 0:
        request.add_data(data)
    try:
        response = urlopen(request)
    except HTTPError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.code)
        sys.exit(5)
    except URLError as e:
        log.error("Something wrong with that url")
        log.error("Error code: %s" % e.reason)
        sys.exit(5)
    except ValueError as e:
        log.error("Try adding http:// before the url")
        sys.exit(5)
    if sys.version_info > (3, 0):
        data = response.read()
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            pass
    else:
        try:
            data = response.read()
        except socket.error as e:
            log.error("Lost the connection to the server")
            sys.exit(5)
    response.close()
    return data

def select_quality(options, streams):
    sort = sorted(streams.keys(), key=int)

    if options.quality:
        quality = options.quality
    else:
        quality = sort.pop()

    try:
        selected = streams[int(quality)]
    except (KeyError, ValueError):
        log.error("Can't find that quality. (Try one of: %s)",
                      ", ".join(map(str, sort)))
        sys.exit(4)

    return selected

