#!/usr/bin/env bash
# echo MESSAGE in blue, run COMMAND with ARGUMENTS in DIRECTORY and
# optionally do a "press enter to continue" thingy
# usage: bash_run.sh [--dont-wait] MESSAGE DIRECTORY COMMAND ARGUMENT ...
# the shebang says bash instead of sh because bash seems to handle SIGINT
# better than Debian's /bin/sh (which is a symlink to /bin/dash)

if test "$1" = --dont-wait; then
    wait=no
    shift
else
    wait=yes
fi

echo -e "\x1b[34m$1\x1b[39m"
cd "$2"
command="$3"
shift 3
"$command" "$@"

if test $wait = yes; then
    echo ""
    echo "-----------------------------"
    echo "Your program completed. Press Enter to close this window..."
    read junk
fi
