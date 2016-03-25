PYLINT_OPTS = --reports=no -d I -d C -d R -d W0511

all: svtplay-dl

clean:
	find . -name '*.pyc' -exec rm {} \;
	rm -f svtplay-dl

pylint:
	pylint $(PYLINT_OPTS) svtplay_dl

export PACKAGES = svtplay_dl \
                 svtplay_dl.fetcher \
                 svtplay_dl.utils \
                 svtplay_dl.service \
                 svtplay_dl.subtitle \
                 svtplay_dl.postprocess
export PYFILES = $(sort $(addsuffix /*.py,$(subst .,/,$(PACKAGES))))

PYTHON ?= /usr/bin/env python

VERSION = $(shell git describe 2>/dev/null || echo $(LATEST_RELEASE)-unknown)

svtplay-dl: $(PYFILES)
	@# Verify that there's no .build already \
	! [ -d .build ] || { \
		echo "ERROR: build already in progress? (or remove $(PWD)/.build/)"; \
		exit 1; \
	}; \
	mkdir -p .build

	@# Stage the files in .build for postprocessing
	for py in $(PYFILES); do \
		install -d ".build/$${py%/*}"; \
		install $$py .build/$$py; \
	done

	# Add git version info to __version__, seen in --version
	sed -i -e 's/^__version__ = "\([^"]\+\)"$$/__version__ = "$(VERSION)"/' \
		.build/svtplay_dl/__init__.py

	@# reset timestamps, to avoid non-determinism in zip file
	find .build/ -exec touch -m -t 198001010000 {} \;

	(cd .build && zip -X --quiet svtplay-dl $(PYFILES))
	(cd .build && zip -X --quiet --junk-paths svtplay-dl svtplay_dl/__main__.py)

	echo '#!$(PYTHON)' > svtplay-dl
	cat .build/svtplay-dl.zip >> svtplay-dl
	rm -rf .build
	chmod a+x svtplay-dl
