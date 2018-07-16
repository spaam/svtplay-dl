all: svtplay-dl

.PHONY: test cover doctest pylint svtplay-dl \
        release clean_releasedir $(RELEASE_DIR)

# These variables describe the latest release:
VERSION = 1.9.11
LATEST_RELEASE = $(VERSION)

# Compress the manual if MAN_GZIP is set to y,
ifeq ($(MAN_GZIP),y)
    MANFILE_EXT = .gz
endif
MANFILE = svtplay-dl.1$(MANFILE_EXT)

# As pod2man is a perl tool, we have to jump through some hoops
# to remove references to perl.. :-)
POD2MAN ?= pod2man --section 1 --utf8 \
                   --center "svtplay-dl manual" \
                   --release "svtplay-dl $(VERSION)" \
                   --date "$(LATEST_RELEASE_DATE)"

PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin

PYTHON ?= /usr/bin/env python3
export PYTHONPATH=lib

# If you don't have a python3 environment (e.g. mock for py3 and
# nosetests3), you can remove the -3 flag.
TEST_OPTS ?= -2 -3

svtplay-dl: $(PYFILES)
	$(MAKE) -C lib
	mv -f lib/svtplay-dl .


svtplay-dl.1: svtplay-dl.pod
	rm -f $@
	$(POD2MAN) $< $@

svtplay-dl.1.gz: svtplay-dl.1
	rm -f $@
	gzip -9 svtplay-dl.1

test:
	sh scripts/run-tests.sh $(TEST_OPTS)

install: svtplay-dl
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)

cover:
	sh scripts/run-tests.sh -C

pylint:
	$(MAKE) -C lib pylint

doctest: svtplay-dl
	sh scripts/diff_man_help.sh

release:
	git tag -m "New version $(NEW_RELEASE)" \
		-m "$$(git log --oneline $$(git describe --tags --abbrev=0 HEAD^)..HEAD^)" \
		$(NEW_RELEASE)

clean:
	$(MAKE) -C lib clean
	rm -f svtplay-dl
	rm -f $(MANFILE)
	rm -rf .tox
