# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# Pylint does not seem to handle conditional imports
# pylint: disable=F0401
# pylint: disable=W0611

from __future__ import absolute_import
from svtplay_dl.utils import is_py3
if is_py3:
    # pylint: disable=E0611
    from urllib.parse import quote, unquote_plus, quote_plus, urlparse, parse_qs, urljoin
    from urllib.request import urlopen, Request, build_opener, \
                               HTTPCookieProcessor, HTTPRedirectHandler
    from urllib.error import HTTPError, URLError
    from urllib.response import addinfourl
    from http.cookiejar import CookieJar, Cookie
else:
    from urllib import addinfourl, quote, unquote_plus, quote_plus
    from urlparse import urlparse, parse_qs, urljoin
    from urllib2 import urlopen, Request, HTTPError, URLError, build_opener, \
                        HTTPCookieProcessor, HTTPRedirectHandler
    from cookielib import CookieJar, Cookie
