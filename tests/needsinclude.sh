#!/bin/bash

set -e

source $(dirname "$BASH_SOURCE")/inclusion.sh

echo this file is $(readlink -f $BASH_SOURCE)
echo i.e. in repository $(dirname $(readlink -f $BASH_SOURCE))

echo $BASH_SOURCE on line $LINENO with args "$@"
