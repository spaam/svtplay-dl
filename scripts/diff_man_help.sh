#!/bin/sh
# Make sure the options listed in --help and the manual are in sync.
TMPDIR=$(mktemp -d svtplay-man-test-XXXXXX)
[ "$TMPDIR" ] || {
	echo "mktemp not available, using static dir"
	TMPDIR=svtplay-man-test.tmp
	[ ! -e "$TMPDIR" ] || {
		echo "$TMPDIR already exists. Aborting."
		exit 1
	}
	mkdir "$TMPDIR"
}
trap 'rm -rf "$TMPDIR"' EXIT TERM

# FIXME: *Currently* we don't have any =head3 that doesn't
# document an option. This is thus fragile to changes.
sed -nre 's/^=head3 //p' svtplay-dl.pod > $TMPDIR/options.man

./svtplay-dl --help | grep '^ *-' > $TMPDIR/options.help

# --help specific filtering
sed -i -re 's/   .*//' $TMPDIR/options.help
sed -i -re 's/  excl.*//' $TMPDIR/options.help
sed -i -re 's/^ *//' $TMPDIR/options.help
sed -i -re 's/OUTPUT/filename/g' $TMPDIR/options.help

for file in $TMPDIR/options.*; do
	sed -i -re 's/, / /' $file
	sed -i -re 's/  / /' $file

	# Normalize order of --help -h vs -h --help
	#  "--help -h"   =>  "-h --help"
	perl -i -pe 's/^(-.(?: [^-][^ ]+)?) (--.*)/\2 \1/' $file
done

OS=$(uname -s)
SHA1="sha1sum"
[ "$OS" = "Darwin*" ] || {
	SHA1="shasum"
}

[ "$($SHA1<$TMPDIR/options.help)" = "$($SHA1<$TMPDIR/options.man)" ] || {
	diff -u $TMPDIR/options.help $TMPDIR/options.man
	exit 1
}
