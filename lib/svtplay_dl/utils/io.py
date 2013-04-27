# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-

# Pylint does not seem to handle conditional imports
# pylint: disable=F0401
# pylint: disable=W0611
# pylint: disable=E0611

from __future__ import absolute_import
import sys

if sys.version_info > (3, 0):
    from io import BytesIO as StringIO
else:
    from StringIO import StringIO
