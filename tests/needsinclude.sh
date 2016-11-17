#!/bin/bash

set -e

source $(dirname "$BASH_SOURCE")/inclusion.sh

echo this file is $(readlink -f $BASH_SOURCE)
echo i.e. in directory $(dirname $(readlink -f $BASH_SOURCE))

echo $BASH_SOURCE on line $LINENO

for arg in "$@"; do
    echo "on HOST=$(hostname), with arg $arg - CWD=$(pwd -P)"
done



