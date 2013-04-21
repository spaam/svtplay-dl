#!/bin/sh

OPTS='--all-modules '

die() {
	echo Error: "$@"
	exit 1
}

COVER_OPTS="--with-coverage --cover-package=svtplay_dl"

while [ "$#" -gt 0 ]; do
	case $1 in
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

PYTHONPATH=lib nosetests $OPTS
