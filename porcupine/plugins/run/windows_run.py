# this is a python script because handling Ctrl+C interrupts in batch
# scripts seems to be impossible

import colorama
import os
import subprocess
import sys


colorama.init()

prog, blue_message, directory, *command = sys.argv
print(colorama.Fore.BLUE + blue_message + colorama.Fore.RESET)
try:
    subprocess.call(command, cwd=directory)
except KeyboardInterrupt:
    # the subprocess should have already printed any traceback or
    # whatever it might want to print
    pass

print()
print("--------------------------")
print("Your program exited. Press Enter to close this window...")
input()
