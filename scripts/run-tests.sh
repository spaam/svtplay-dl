#!/bin/sh

OPTS='--all-modules --with-doctest '

die() {
	echo Error: "$@"
	exit 1
}

COVER_OPTS="--with-coverage --cover-package=svtplay_dl"

NOSETESTS=

while [ "$#" -gt 0 ]; do
	case $1 in
		-2)
			NOSETESTS="$NOSETESTS nosetests"
			;;
		-3)
			NOSETESTS="$NOSETESTS nosetests3"
			;;
		-c|--coverage)
			OPTS="$OPTS $COVER_OPTS"
			;;
		-C|--coverage-html)
			OPTS="$OPTS $COVER_OPTS --cover-html"
			;;
		-v|--verbose)
			OPTS="$OPTS --verbose"
			;;
		-*)
			die "Unknown option: '$1'"
			;;
		*)
			die "Unknown argument: '$1'"
			;;
	esac
	shift
done

# Default to only run for python2
NOSETESTS=${NOSETESTS:-nosetests}

tests_ok=y
for nose in $NOSETESTS; do
	PYTHONPATH=lib $nose $OPTS
	[ $? -eq 0 ] || tests_ok=
done

[ "$tests_ok" = y ]
