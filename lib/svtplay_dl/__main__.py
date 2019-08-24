#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
import sys

if __package__ is None and not hasattr(sys, "frozen"):
    # direct call of __main__.py
    import os.path

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import svtplay_dl

if __name__ == "__main__":
    svtplay_dl.main()
