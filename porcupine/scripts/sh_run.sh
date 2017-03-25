#!/bin/sh
# run a python file
# usage: /path/to/sh_run.sh /PATH/TO/PYTHON DIRNAME BASENAME.py

cd "$2"
"$1" "$3"

echo
echo "-----------------------------"
echo "Your program completed. Press Enter to close this window..."
read junk
