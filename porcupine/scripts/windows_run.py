# this is a python script because handling Ctrl+C interrupts in batch
# scripts seems to be impossible

import os
import subprocess
import sys

prog, path = sys.argv
dirname, basename = os.path.split(path)
try:
    subprocess.call([sys.executable, basename], cwd=dirname)
except KeyboardInterrupt:
    # the subprocess already printed the traceback
    pass

print()
print("--------------------------")
print("Your program exited. Press Enter to close this window...")
input()
