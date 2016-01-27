# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# Pylint does not seem to handle conditional imports
# pylint: disable=F0401
# pylint: disable=W0611
# pylint: disable=E0611

from __future__ import absolute_import
from svtplay_dl.utils import is_py2

if is_py2:
    from StringIO import StringIO
else:
    from io import StringIO

