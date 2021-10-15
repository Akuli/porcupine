# this is a python script because handling Ctrl+C interrupts in batch
# scripts seems to be impossible
#
# This should always run in the same python that Porcupine uses.
from __future__ import annotations

import subprocess
import sys

import colorama

colorama.init()

prog, directory, command = sys.argv
print(colorama.Fore.BLUE + command + colorama.Fore.RESET)
try:
    returncode: int | None = subprocess.call(command, cwd=directory, shell=True)
except KeyboardInterrupt:
    # the subprocess should have already printed any traceback or
    # whatever it might want to print
    # TODO: try to catch the return code in this case as well?
    returncode = None

print()
print("-----------------------------")
if returncode == 0:
    print("The program completed successfully.")
elif returncode is None:
    print("The program was interrupted.")
else:
    print(f"The program failed with status {returncode}.")

print("Press Enter to close this window...")
input()
