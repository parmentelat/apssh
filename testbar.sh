#!/bin/bash

# this time we expect arguments
# test with e.g.
# bin/apssh -u root -t "faraday.inria.fr bemol.pl.sophia.inria.fr" -f testbar.sh one two three

COMMAND=$(basename $0)
DIRNAME=$(dirname $0)
HOST=$(hostname)
CWD=$(pwd -P)

echo ENTERING COMMAND $COMMAND

for arg in "$@"; do
    echo "host=$HOST, with arg $arg, in $CWD"
done
