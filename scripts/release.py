#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.append("")  # import from current working directory
from porcupine import version_info as old_info

TAG_FORMAT = "v%d.%d.%d"


def replace_in_file(path, old, new):
    content = path.read_text()
    assert content.count(old) >= 1
    path.write_text(content.replace(old, new))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "what_to_bump",
        choices=["major", "minor", "patch"],
        help="which part of major.minor.patch version number to increment",
    )
    args = parser.parse_args()

    if args.what_to_bump == "major":
        new_info = (old_info[0] + 1, 0, 0)
    elif args.what_to_bump == "minor":
        new_info = (old_info[0], old_info[1] + 1, 0)
    elif args.what_to_bump == "patch":
        new_info = (old_info[0], old_info[1], old_info[2] + 1)
    else:
        assert False, f"unexpected what_to_bump {args.what_to_bump!r}"

    # https://stackoverflow.com/a/1593487
    branch = subprocess.check_output("git symbolic-ref --short HEAD", shell=True).decode().strip()
    assert branch in ("master", "bugfix-release")

    # If this fails you have uncommitted changes
    for line in subprocess.check_output("git status --porcelain", shell=True).splitlines():
        assert line.startswith(b"?? "), line

    assert "VIRTUAL_ENV" in os.environ
    with open("CHANGELOG.md") as changelog:
        assert changelog.read().split("\n\n\n")[1].startswith(f"## {TAG_FORMAT % new_info}")

    print(f"Version changes: {TAG_FORMAT % old_info}  --->  {TAG_FORMAT % new_info}")

    replace_in_file(Path("porcupine/__init__.py"), repr(old_info), repr(new_info))
    replace_in_file(Path("README.md"), TAG_FORMAT % old_info, TAG_FORMAT % new_info)
    subprocess.check_call(["git", "add", "porcupine/__init__.py", "README.md", "CHANGELOG.md"])
    subprocess.check_call(["git", "commit", "-m", f"Version {TAG_FORMAT % new_info}"])
    subprocess.check_call(["git", "tag", TAG_FORMAT % new_info])
    subprocess.check_call(["git", "push", "origin", branch])
    subprocess.check_call(["git", "push", "--tags", "origin", branch])


if __name__ == "__main__":
    main()
