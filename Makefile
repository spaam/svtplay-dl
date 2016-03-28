all: svtplay-dl

.PHONY: test cover doctest pylint svtplay-dl \
        release clean_releasedir $(RELEASE_DIR)

# These variables describe the latest release:
VERSION = 1.0
LATEST_RELEASE = $(VERSION)

# If we build a new release, this is what it will be called:
NEW_RELEASE = $(VERSION)
RELEASE_DIR = svtplay-dl-$(NEW_RELEASE)

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
POD2MAN ?= pod2man --section 1 --utf8 \
                   --center "svtplay-dl manual" \
                   --release "svtplay-dl $(VERSION)" \
                   --date "$(LATEST_RELEASE_DATE)"

PYTHON ?= /usr/bin/env python
export PYTHONPATH=lib

# If you don't have a python3 environment (e.g. mock for py3 and
# nosetests3), you can remove the -3 flag.
TEST_OPTS ?= -2 -3

install: svtplay-dl $(MANFILE)
	install -d $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(MANDIR)
	install -m 755 svtplay-dl $(DESTDIR)$(BINDIR)
	install -m 644 $(MANFILE) $(DESTDIR)$(MANDIR)

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
	sh scripts/run-tests.sh $(TEST_OPTS)

cover:
	sh scripts/run-tests.sh -C

pylint:
	$(MAKE) -C lib pylint

doctest: svtplay-dl
	sh scripts/diff_man_help.sh

$(RELEASE_DIR): clean_releasedir
	mkdir $(RELEASE_DIR)
	cd $(RELEASE_DIR) && git clone -b master ../ . && \
		make $(MANFILE)

clean_releasedir:
	rm -rf $(RELEASE_DIR)

release: $(RELEASE_DIR) release-test
	set -e; cd $(RELEASE_DIR) && \
		sed -i -re 's/^(__version__ = ).*/\1"$(NEW_RELEASE)"/' lib/svtplay_dl/__init__.py;\
		git add Makefile lib/svtplay_dl/__init__.py; \
		git commit -m "New release $(NEW_RELEASE)";
	(cd $(RELEASE_DIR) && git format-patch --stdout HEAD^) | git am

	git tag -m "New version $(NEW_RELEASE)" \
		-m "$$(git log --oneline $$(git describe --tags --abbrev=0 HEAD^)..HEAD^)" \
		$(NEW_RELEASE)

	make clean_releasedir

release-test: $(RELEASE_DIR)
	make -C $(RELEASE_DIR) test
	make -C $(RELEASE_DIR) doctest

clean:
	$(MAKE) -C lib clean
	rm -f svtplay-dl
	rm -f $(MANFILE)
