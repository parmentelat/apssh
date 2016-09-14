#!/bin/bash
message=$1
delay=$(( $RANDOM / 8000)); echo $message: waiting for 0.${delay}s on $(hostname) ; perl -e "select(undef,undef,undef,0.${delay});"; echo $message done on $(hostname)
