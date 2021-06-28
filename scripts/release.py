#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import pathlib
import subprocess
import sys

sys.path.append("")
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

    status = subprocess.check_output(["git", "status"])
    assert status.startswith(b"On branch master\n")
    assert b"Changes not staged for commit:" not in status
    assert "VIRTUAL_ENV" in os.environ

    print(f"Version changes: {TAG_FORMAT % old_info}  --->  {TAG_FORMAT % new_info}")

    replace_in_file(pathlib.Path("porcupine/__init__.py"), repr(old_info), repr(new_info))
    replace_in_file(pathlib.Path("README.md"), TAG_FORMAT % old_info, TAG_FORMAT % new_info)
    subprocess.check_call(["git", "add", "porcupine/__init__.py", "README.md"])
    subprocess.check_call(["git", "commit", "-m", f"Version {TAG_FORMAT % new_info}"])
    subprocess.check_call(["git", "tag", TAG_FORMAT % new_info])
    subprocess.check_call(["git", "push", "origin", "master"])
    subprocess.check_call(["git", "push", "--tags", "origin", "master"])


if __name__ == "__main__":
    main()
