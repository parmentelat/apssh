#!/bin/bash

loops=$1; shift

[ -n "$loops" ] || loops=10

for i in $(seq $loops); do
    echo STDOUT $i
    >&2 echo STDERR $i
done
