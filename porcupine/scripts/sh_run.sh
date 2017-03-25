#!/bin/sh
cd "$2"
"$1" "$3"

echo
echo "-----------------------------"
echo "Your program completed. Press Enter to close this window..."
read junk
