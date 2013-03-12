#!/bin/sh

OPTS='--all-modules '

die() {
	echo Error: "$@"
	exit 1
}

while [ "$#" -gt 0 ]; do
	case $1 in
		-c|--coverage)
			OPTS="$OPTS --with-coverage"
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
