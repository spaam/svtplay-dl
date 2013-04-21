all: svtplay-dl

.PHONY: test cover pylint

clean:
	rm -f svtplay-dl

PREFIX?=/usr/local
BINDIR=$(PREFIX)/bin
PYTHON=/usr/bin/env python
export PYTHONPATH=lib

install: svtplay-dl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)

svtplay-dl: lib/svtplay_dl/*py lib/svtplay_dl/fetcher/*py lib/svtplay_dl/service/*py
	cd lib; $(MAKE)
	mv lib/svtplay-dl .

test:
	sh run-tests.sh

cover:
	sh run-tests.sh -C

pylint:
	find lib -name '*.py' -a '!' -path '*/tests/*' | xargs pylint
