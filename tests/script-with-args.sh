#!/bin/bash

# this time we expect arguments
# test with e.g.
# bin/apssh -u root -t "faraday.inria.fr bemol.pl.sophia.inria.fr" -f testbar.sh one two three

ZERO=$0
COMMAND=$(basename $0)
DIRNAME=$(dirname $0)

echo "ENTERING COMMAND $COMMAND (full name $ZERO)"

for arg in "$@"; do
    echo "on HOST=$(hostname), with arg $arg - CWD=$(pwd -P)"
done
