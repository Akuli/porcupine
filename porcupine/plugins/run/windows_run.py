# this is a python script because handling Ctrl+C interrupts in batch
# scripts seems to be impossible
#
# This should always run in the same python that Porcupine uses.

import os
import subprocess
import sys
from typing import Optional

import colorama  # type: ignore[import]

colorama.init()

# When installed from the exe installer, python finds its modules with
# PYTHONPATH. We don't want to pass it on to the user's command, because it
# should run with the user's own Python, not Porcupine's python.
new_env = dict(os.environ)
try:
    del new_env['PYTHONPATH']
except KeyError:
    pass

prog, blue_message, directory, *command = sys.argv
print(colorama.Fore.BLUE + blue_message + colorama.Fore.RESET)
try:
    returncode: Optional[int] = subprocess.call(command, cwd=directory, env=new_env)
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
    print("The program failed with status %d." % returncode)

print("Press Enter to close this window...")
input()
