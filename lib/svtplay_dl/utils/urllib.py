# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# This module is a python2/3 compat glue, we don't use the imports
# here.
# pylint: disable=unused-import

# Pylint does not seem to handle conditional imports
# pylint: disable=no-name-in-module
# pylint: disable=import-error

from __future__ import absolute_import
from svtplay_dl.utils import is_py2
if is_py2:
    from urllib import quote, unquote_plus, quote_plus
    from urlparse import urlparse, parse_qs, urljoin
else:
    from urllib.parse import quote, unquote_plus, quote_plus, urlparse, parse_qs, urljoin
