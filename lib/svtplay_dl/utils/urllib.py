# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# Pylint does not seem to handle conditional imports
# pylint: disable=F0401
# pylint: disable=W0611

from __future__ import absolute_import
import sys

if sys.version_info > (3, 0):
    # pylint: disable=E0611
    from urllib.parse import unquote_plus, quote_plus, urlparse, parse_qs
    from urllib.request import urlopen, Request, build_opener, \
                               HTTPCookieProcessor, HTTPRedirectHandler
    from urllib.error import HTTPError, URLError
    from urllib.response import addinfourl
    from http.cookiejar import CookieJar, Cookie
else:
    from urllib import addinfourl, unquote_plus, quote_plus
    from urlparse import urlparse, parse_qs
    from urllib2 import urlopen, Request, HTTPError, URLError, build_opener, \
                        HTTPCookieProcessor, HTTPRedirectHandler
    from cookielib import CookieJar, Cookie
