#!/bin/bash
message=$1
delay=$(( $RANDOM / 8000)); echo $message: waiting for $delay on $(hostname) ; sleep $delay; echo $message done on $(hostname)
