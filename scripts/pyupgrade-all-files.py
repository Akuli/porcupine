#!/usr/bin/env python3

"""This script runs pyupgrade on all files.

It is needed because pyupgrade does not accept a directory as argument, and
needs individual files.
"""

import os
import subprocess
import sys
from pathlib import Path

# Go to project root
os.chdir(Path(__file__).absolute().parent.parent)

command = ['pyupgrade', '--keep-runtime-typing', '--py310-plus']

# Get Python files from git
for path in subprocess.check_output(['git', 'ls-files'], text=True).splitlines():
    if path.endswith(('.py', '.pyw')):
        command.append(path)

sys.exit(subprocess.call(command))
