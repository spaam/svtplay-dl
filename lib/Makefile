all: svtplay-dl

clean:
	rm -f svtplay-dl

export PACKAGES = svtplay_dl \
                 svtplay_dl.fetcher \
                 svtplay_dl.utils \
                 svtplay_dl.service
export PYFILES = $(addsuffix /*.py,$(subst .,/,$(PACKAGES)))

PREFIX=/usr/local
BINDIR=$(PREFIX)/bin
PYTHON=/usr/bin/env python

install: svtplay-dl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)

svtplay-dl: $(PYFILES)
	zip --quiet svtplay-dl $(PYFILES)
	zip --quiet --junk-paths svtplay-dl svtplay_dl/__main__.py
	echo '#!$(PYTHON)' > svtplay-dl
	cat svtplay-dl.zip >> svtplay-dl
	rm svtplay-dl.zip
	chmod a+x svtplay-dl
