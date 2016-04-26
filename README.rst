svtplay-dl
==========

Installation
------------

Mac OSX
~~~~~~~

If you have OS X and `Homebrew`_ you can install with:

::

    brew install svtplay-dl

Debian and Ubuntu
~~~~~~~~~~~~~~~~~

svtplay-dl is available in Debian in Jessie and later and Ubuntu in
14.04 and later, which means you can install it using apt:

::

    apt-get install svtplay-dl

… as root.

Windows
~~~~~~~

You can download windows binaries from `svtplay-dl.se`_

Other systems with python
~~~~~~~~~~~~~~~~~~~~~~~~~


::

    pip install svtplay-dl

From source
~~~~~~~~~~~

If packaging isn’t available for your operating system, or you want to
use a non-released version, you’ll want to install from source. Use git
to download the sources:

::

    git clone git://github.com/spaam/svtplay-dl

svtplay-dl requires the following additional tools and libraries. They
are usually available from your distribution’s package repositories. If
you don’t have them, some features will not be working.

-  `RTMPDump`_ 2.4 or higher to download RTMP streams.
-  `PyCrypto`_ to download encrypted HLS streams
-  `Requests`_
- `ffmpeg`_ or `avconv`_ for postprocessing and/or for DASH streams

To install it, run

::

    # as root:
    python setup.py install

    # or the old method
    make

    # as root:
    make install

After install
~~~~~~~~~~~~~
::

    svtplay-dl [options] URL


If you encounter any bugs or problems, don’t hesitate to open an issue
`on github`_. Or why not join the ``#svtplay-dl`` IRC channel on Freenode?

Supported services
------------------

This script works for:

-  aftonbladet.se
-  bambuser.com
-  comedycentral.se
-  dbtv.no
-  di.se
-  dn.se
-  dplay.se
-  dr.dk
-  efn.se
-  expressen.se
-  hbo.com
-  kanal9play.se
-  nickelodeon.nl
-  nickelodeon.no
-  nickelodeon.se
-  nrk.no
-  oppetarkiv.se
-  ruv.is
-  svd.se
-  sverigesradio.se
-  svtplay.se
-  tv10play.se
-  tv3play.dk
-  tv3play.ee
-  tv3play.lt
-  tv3play.lv
-  tv3play.no
-  tv3play.se
-  tv4.se
-  tv4play.se
-  tv6play.se
-  tv8play.se
-  twitch.tv
-  ur.se
-  urplay.se
-  vg.no
-  viagame.com
-  viasat4play.no

License
-------

This project is licensed under `The MIT License (MIT)`_.
Homepage: `svtplay-dl.se`_

.. _Homebrew: http://brew.sh/
.. _RTMPDump: http://rtmpdump.mplayerhq.hu/
.. _PyCrypto: https://www.dlitz.net/software/pycrypto/
.. _Requests: http://www.python-requests.org/
.. _ffmpeg: https://ffmpeg.org
.. _avconv: https://libav.org
.. _on github: https://github.com/spaam/svtplay-dl/issues
.. _svtplay-dl.se: https://svtplay-dl.se
.. _The MIT License (MIT): LICENSE

