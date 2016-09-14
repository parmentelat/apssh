delay=$(( $RANDOM / 8000)); echo waiting for 0.${delay}s on $(hostname) ; perl -e "select(undef,undef,undef,0.${delay});"; echo done on $(hostname)
