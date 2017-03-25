#!/usr/bin/env bash
# run a python file
# usage: /path/to/sh_run.sh /PATH/TO/PYTHON DIRNAME BASENAME.py
# the shebang says bash instead of sh because bash seems to handle
# SIGINT better than Debian's /bin/sh (which is a symlink to /bin/dash)

cd "$2"
"$1" "$3"

echo
echo "-----------------------------"
echo "Your program completed. Press Enter to close this window..."
read junk
