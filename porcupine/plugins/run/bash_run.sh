#!/usr/bin/env bash
# usage: ./bash_run.sh [--dont-wait] DIRECTORY COMMAND
# echo MESSAGE in blue, run COMMAND with ARGUMENTS in DIRECTORY and
# optionally do a "press enter to continue" thingy
#
# the shebang says bash instead of sh because bash seems to handle SIGINT
# better than Debian's /bin/sh (which is a symlink to /bin/dash)

if [ "$1" = --dont-wait ]; then
    wait=no
    shift
else
    wait=yes
fi

echo -e "\x1b[34m$2\x1b[39m"
cd "$1"
eval "$2"
returncode=$?

echo ""
echo "-----------------------------"
if [ $returncode = 0 ]; then
    echo "The program completed successfully."
else
    echo "The program failed with status $returncode."
fi

if [ $wait = yes ]; then
    echo "Press Enter to close this window..."
    read junk
fi
