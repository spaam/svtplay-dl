all: svtplay-dl

.PHONY: test cover doctest pylint svtplay-dl \
        release clean_releasedir $(RELEASE_DIR)

VERSION = 0.10
RELEASE = $(VERSION).$(shell date +%Y.%m.%d)
RELEASE_DIR = svtplay-dl-$(RELEASE)
LATEST_RELEASE = 0.10.2015.03.25

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
	sh run-tests.sh $(TEST_OPTS)

cover:
	sh run-tests.sh -C

pylint:
	$(MAKE) -C lib pylint

doctest: svtplay-dl
	sh scripts/diff_man_help.sh

$(RELEASE_DIR): clean_releasedir
	mkdir svtplay-dl-$(RELEASE)
	cd svtplay-dl-$(RELEASE) && git clone -b master ../ . && make svtplay-dl

clean_releasedir:
	rm -rf $(RELEASE_DIR)

release: $(RELEASE_DIR) release-test
	set -e; cd $(RELEASE_DIR) && \
		sed -i -r -e 's/^(LATEST_RELEASE = ).*/\1$(RELEASE)/' Makefile;\
		sed -i -r -e 's/^(__version__ = ).*/\1"$(RELEASE)"/' lib/svtplay_dl/__init__.py;\
		make svtplay-dl; \
		git add svtplay-dl Makefile lib/svtplay_dl/__init__.py; \
		git commit -m "Prepare for release $(RELEASE)";
	(cd $(RELEASE_DIR) && git format-patch --stdout HEAD^) | git am

	git tag -m "New version $(RELEASE)" \
		-m "$$(git log --oneline $(LATEST_RELEASE)..HEAD^)" \
		$(RELEASE)

	make clean_releasedir

release-test: $(RELEASE_DIR)
	make -C $(RELEASE_DIR) test
	make -C $(RELEASE_DIR) doctest

clean:
	$(MAKE) -C lib clean
	rm -f svtplay-dl
	rm -f $(MANFILE)
