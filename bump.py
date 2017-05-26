#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import subprocess

from porcupine import version_info as old_info


def bump_version(new_info, commit_message):
    path = os.path.join('porcupine', '__init__.py')
    with open(path, 'r') as f:
        content = f.read()
    assert repr(old_info) in content

    content = content.replace(repr(old_info), repr(new_info), 1)
    with open(path, 'w') as f:
        f.write(content)

    subprocess.call(['git', 'add', path])
    subprocess.call(['git', 'commit', '-m', commit_message])
    subprocess.call(['git', 'tag', 'v%d.%d.%d' % new_info])
    print("Bumped version from %d.%d.%d to %d.%d.%d" % (old_info + new_info))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'what_to_bump', choices=['major', 'minor', 'patch'],
        help="which part of major.minor.patch version number to increment")
    parser.add_argument(
        '-m', '--message', default='bump version', help="git commit message")
    args = parser.parse_args()

    if args.what_to_bump == 'major':
        new_info = (old_info[0]+1, 0, 0)
    elif args.what_to_bump == 'minor':
        new_info = (old_info[0], old_info[1]+1, 0)
    elif args.what_to_bump == 'patch':
        new_info = (old_info[0], old_info[1], old_info[2]+1)
    else:
        assert False, "unexpected args.what_to_bump %r" % args.what_to_bump

    bump_version(new_info, args.message)


if __name__ == '__main__':
    main()
