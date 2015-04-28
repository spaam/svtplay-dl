# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# Pylint does not seem to handle conditional imports
# pylint: disable=F0401
# pylint: disable=W0611
# pylint: disable=E0611

from __future__ import absolute_import
from svtplay_dl.utils import is_py3

if is_py3:
    from io import StringIO
else:
    from StringIO import StringIO
