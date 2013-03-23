#!/usr/bin/env python
import sys

if __package__ is None and not hasattr(sys, "frozen"):
    # direct call of __main__.py
    import os.path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import svtplay_dl

if __name__ == '__main__':
    svtplay_dl.main()
