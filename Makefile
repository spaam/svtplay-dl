all: svtplay-dl

.PHONY: test cover pylint svtplay-dl

clean:
	rm -f svtplay-dl

PREFIX?=/usr/local
BINDIR=$(PREFIX)/bin
PYTHON=/usr/bin/env python
export PYTHONPATH=lib

# Disable convention, refactor, and TODO warnings
PYLINT_OPTS = -d C -d R -d W0511

install: svtplay-dl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)

svtplay-dl: $(PYFILES)
	$(MAKE) -C lib
	mv lib/svtplay-dl .

test:
	sh run-tests.sh

cover:
	sh run-tests.sh -C

pylint:
	find lib -name '*.py' -a '!' -path '*/tests/*' | xargs pylint $(PYLINT_OPTS)
