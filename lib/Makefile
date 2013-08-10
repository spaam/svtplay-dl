all: svtplay-dl

clean:
	find . -name '*.pyc' -exec rm {} \;
	rm -f svtplay-dl

export PACKAGES = svtplay_dl \
                 svtplay_dl.fetcher \
                 svtplay_dl.utils \
                 svtplay_dl.service
export PYFILES = $(addsuffix /*.py,$(subst .,/,$(PACKAGES)))

PYTHON = /usr/bin/env python

svtplay-dl: $(PYFILES)
	zip --quiet svtplay-dl $(PYFILES)
	zip --quiet --junk-paths svtplay-dl svtplay_dl/__main__.py
	echo '#!$(PYTHON)' > svtplay-dl
	cat svtplay-dl.zip >> svtplay-dl
	rm svtplay-dl.zip
	chmod a+x svtplay-dl
