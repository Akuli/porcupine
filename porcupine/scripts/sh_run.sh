#!/bin/sh
usage="Usage: $0 [-w|--wait] /PATH/TO/PYTHON DIRNAME BASENAME.py"

wait=no
case "$1" in
    -w|--wait)
        wait=yes
        shift
        ;;
    -*)
        # unknown option
        echo "$usage"
        exit 2
        ;;
esac
if test $# -ne 3; then
    echo "$usage"
    exit 2
fi

cd "$2"
"$1" "$3"

if test $wait = yes; then
    echo
    echo "-----------------------------"
    echo "Your program completed. Press Enter to close this window..."
    read junk
fi
