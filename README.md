# svtplay-dl


## Installation

### MacOS

If you have [Homebrew](https://brew.sh/) on your machine you can install by running:

```
    brew install svtplay-dl
```
You will need to run `brew install ffmpeg` or `brew install libav` afterwards, if you don't already have one of these packages.

### Debian and Ubuntu

svtplay-dl is available in Debian Jessie and later and on Ubuntu 14.04 and later, which means you can install it straight away using apt. The version in their repo is often old and thus we **strongly** recommend using our own apt repo, which always include the latest version. The svtplay-dl repo for Debian / Ubuntu can be found at [apt.svtplay-dl.se](https://apt.svtplay-dl.se/). 

##### Add the release PGP keys:
```
    curl -s https://svtplay-dl.se/release-key.txt | sudo apt-key add -
```

##### Add the "release" channel to your APT sources:
```  
    echo "deb https://apt.svtplay-dl.se/ svtplay-dl release" | sudo tee /etc/apt/sources.list.d/svtplay-dl.list
```
    
##### Update and install svtplay-dl:
``` 
    sudo apt-get update

    sudo apt-get install svtplay-dl
```

### Solus

svtplay-dl is avaliable in the stable repository of [Solus](https://solus-project.com/) and can be installed by running:

```
sudo eopkg it svtplay-dl
```

### Windows

You can download the Windows binaries from [svtplay-dl.se](https://svtplay-dl.se/)

If you want to build your own Windows binaries:

1. Install [cx_freeze](https://anthony-tuininga.github.io/cx_Freeze/)
3. Follow the steps listed under [From source](#from-source)
4. cd path\to\svtplay-dl && mkdir build
5. `python setversion.py`  # this will change the version string to a more useful one
5. `python %PYTHON%\\Scripts\\cxfreeze --include-modules=queue,idna.idnadata --target-dir=build bin/svtplay-dl`
6. Find binary in build folder. you need `svtplay-dl.exe` and `pythonXX.dll` from that folder to run `svtplay-dl.exe`

### Other systems with python

```
    pip3 install svtplay-dl
```

### Any UNIX (Linux, BSD, macOS, etc.) 

##### Download with curl
```
sudo curl -L https://svtplay-dl.se/download/latest/svtplay-dl -o /usr/local/bin/svtplay-dl
```

##### Make it executable
```
sudo chmod a+rx /usr/local/bin/svtplay-dl
```

### From source

If packaging isn’t available for your operating system, or you want to
use a non-released version, you’ll want to install from source. Use git
to download the sources:

```
    git clone https://github.com/spaam/svtplay-dl
```

svtplay-dl requires the following additional tools and libraries. They
are usually available from your distribution’s package repositories. If
you don’t have them, some features will not be working.

-  [Python](https://www.python.org/) 3.4 or higher
-  [RTMPDump](https://rtmpdump.mplayerhq.hu/) 2.4 or higher to download RTMP streams.
-  [pycryptodome](https://www.pycryptodome.org/en/latest/) to download encrypted HLS streams
-  [PyYaml](https://github.com/yaml/pyyaml) for configure file
-  [Requests](http://www.python-requests.org/)
-  [PySocks](https://github.com/Anorov/PySocks) to enable proxy support
-  [ffmpeg](https://ffmpeg.org) or [avconv](https://libav.org/) for postprocessing and/or for DASH streams

##### To install it, run:

```
    sudo python3 setup.py install
```

## After install

```
    svtplay-dl [options] URL
```

If you encounter any bugs or problems, don’t hesitate to open an issue [on github](https://github.com/spaam/svtplay-dl/issues).
Or why not join the ``#svtplay-dl`` IRC channel on Freenode?

## Supported services

This script works for:

-  aftonbladet.se
-  bambuser.com
-  comedycentral.se
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

## License

This project is licensed under [The MIT License (MIT)](LICENSE)
Homepage: [svtplay-dl.se](https://svtplay-dl.se/)
