all: svtplay-dl

.PHONY: test cover pylint svtplay-dl

VERSION = 0.9

PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1

# Compress the manual if MAN_GZIP is set to y,
ifeq ($(MAN_GZIP),y)
    MANFILE_EXT = .gz
endif
MANFILE = svtplay-dl.1$(MANFILE_EXT)

# As pod2man is a perl tool, we have to jump through some hoops
# to remove references to perl.. :-)
POD2MAN ?= pod2man --section 1 --utf8 -c "svtplay-dl manual" \
           -r "svtplay-dl $(VERSION)"

PYTHON ?= /usr/bin/env python
export PYTHONPATH=lib

# Disable convention, refactor, and TODO warnings
PYLINT_OPTS = -d I -d C -d R -d W0511

# If you don't have a python3 environment (e.g. mock for py3 and
# nosetests3), you can remove the -3 flag.
TEST_OPTS = -2 -3

install: svtplay-dl $(MANFILE)
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(MANDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)
	install -m 755 $(MANFILE) $(DESTDIR)$(MANDIR)

svtplay-dl: $(PYFILES)
	$(MAKE) -C lib
	mv lib/svtplay-dl .

svtplay-dl.1: svtplay-dl.pod
	rm -f $@
	$(POD2MAN) $< $@

svtplay-dl.1.gz: svtplay-dl.1
	rm -f $@
	gzip -9 svtplay-dl.1

test:
	sh run-tests.sh $(TEST_OPTS)

cover:
	sh run-tests.sh -C

pylint:
	find lib -name '*.py' -a '!' -path '*/tests/*' | xargs pylint $(PYLINT_OPTS)

clean:
	$(MAKE) -C lib clean
	rm -f svtplay-dl
	rm -f $(MANFILE)
