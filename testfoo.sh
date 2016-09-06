#!/bin/bash

# no arguments expected
# test with e.g.
# bin/apssh -u root -t "faraday.inria.fr bemol.pl.sophia.inria.fr" -f testfoo.sh

cat /etc/fedora-release /etc/lsb-release /etc/rhubarbe-version 2> /dev/null
hostname
