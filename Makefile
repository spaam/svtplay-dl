all: svtplay-dl

clean:
	rm -f svtplay-dl

PREFIX=/usr/local
BINDIR=$(PREFIX)/bin
PYTHON=/usr/bin/env python

install: svtplay-dl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)

svtplay-dl: lib/svtplay_dl/*py lib/svtplay_dl/fetcher/*py lib/svtplay_dl/service/*py
	zip --quiet svtplay-dl lib/svtplay_dl/*py lib/svtplay_dl/fetcher/*py lib/svtplay_dl/service/*py
	zip --quiet --junk-paths svtplay-dl lib/svtplay_dl/__main__.py
	echo '#!$(PYTHON)' > svtplay-dl
	cat svtplay-dl.zip >> svtplay-dl
	rm svtplay-dl.zip
	chmod a+x svtplay-dl
