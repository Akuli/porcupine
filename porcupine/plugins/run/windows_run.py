# this is a python script because handling Ctrl+C interrupts in batch
# scripts seems to be impossible

import colorama
import subprocess
import sys


colorama.init()

prog, blue_message, directory, *command = sys.argv
print(colorama.Fore.BLUE + blue_message + colorama.Fore.RESET)
try:
    returncode = subprocess.call(command, cwd=directory)
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
