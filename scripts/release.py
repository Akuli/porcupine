#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.append("")  # import from current working directory
from porcupine import version_info as old_info

TAG_FORMAT = "v%d.%02d.%02d"


def replace_in_file(path, old, new):
    content = path.read_text()
    assert content.count(old) >= 1
    path.write_text(content.replace(old, new))


def main():
    dt = datetime.now()
    new_info = (dt.year, dt.month, dt.day)
    assert new_info > old_info

    # https://stackoverflow.com/a/1593487
    branch = subprocess.check_output("git symbolic-ref --short HEAD", shell=True).decode().strip()
    assert branch in ("main", "bugfix-release")

    # If this fails you have uncommitted changes
    for line in subprocess.check_output("git status --porcelain", shell=True).splitlines():
        assert line.startswith(b"?? "), line

    assert "VIRTUAL_ENV" in os.environ

    changelog = Path("CHANGELOG.md").read_text()
    assert changelog.split("\n\n\n")[1].startswith("## Unreleased")
    assert changelog.count("Unreleased") == 1

    print(f"Version changes: {TAG_FORMAT % old_info}  --->  {TAG_FORMAT % new_info}")

    replace_in_file(Path("CHANGELOG.md"), "Unreleased", TAG_FORMAT % new_info)
    replace_in_file(Path("porcupine/__init__.py"), repr(old_info), repr(new_info))
    replace_in_file(Path("README.md"), TAG_FORMAT % old_info, TAG_FORMAT % new_info)
    subprocess.check_call(["git", "add", "porcupine/__init__.py", "README.md", "CHANGELOG.md"])
    subprocess.check_call(["git", "commit", "-m", f"Version {TAG_FORMAT % new_info}"])
    subprocess.check_call(["git", "tag", TAG_FORMAT % new_info])
    subprocess.check_call(["git", "push", "origin", branch])
    subprocess.check_call(["git", "push", "--tags", "origin", branch])


if __name__ == "__main__":
    main()
