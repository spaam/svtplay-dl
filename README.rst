svtplay-dl
==========

Installation
------------

Mac OSX
~~~~~~~

If you have OS X and `Homebrew`_ you can install with:

::

    brew install svtplay-dl
    Make sure you notice that you need to run `brew install ffmpeg` or `brew install libav` afterwards, if you don't already have one of these packages.

Debian and Ubuntu
~~~~~~~~~~~~~~~~~

svtplay-dl(v 0.30) is available in Debian in Jessie and later and Ubuntu in
14.04 and later, which means you can install it straight away using apt (even though version included in the official Debian and Ubuntu apt repos is very old and we **strongly** recommend using our own apt repo which always include the latest version.)

    **svtplay-dl apt repo for debian / ubuntu (https://apt.svtplay-dl.se/)**
    
    # Add the release PGP keys:
    
    curl -s https://svtplay-dl.se/release-key.txt | sudo apt-key add -

    # Add the "release" channel to your APT sources:
    
    echo "deb http://apt.svtplay-dl.se/ svtplay-dl release" | sudo tee /etc/apt/sources.list.d/svtplay-dl.list


    # Update and install svtplay-dl:
    
    sudo apt-get update
    
    sudo apt-get install svtplay-dl
    
… as root.

Windows
~~~~~~~

You can download windows binaries from `svtplay-dl.se`_

If you want to build your own windows binaries:

1. Install pyinstaller 3.1.1 (https://pypi.python.org/pypi/PyInstaller/3.1.1)
2. Follow the steps listed under **From source**
3. Run 
::
    pyinstaller.exe --noupx --onefile c:\path\to\svtplay-dl-clone\spec\svtplay-dl.spec  (where you replace the path with the correct one)
4. Find binary in dist folder. 

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
-  viafree.se (former tv3play.se, tv6play.se, tv8play.se, tv10play.se)
-  viafree.dk (former tv3play.dk)
-  viafree.no (former tv3play.no, viasat4play.no)
-  tv3play.ee
-  tv3play.lt
-  tv3play.lv
-  tv4.se
-  tv4play.se
-  twitch.tv
-  ur.se
-  urplay.se
-  vg.no
-  viagame.com

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

