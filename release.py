#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import subprocess
import sys

from porcupine import version_info as old_info


def check_stuff():
    status = subprocess.check_output(['git', 'status'])
    assert status.startswith(b'On branch master\n')
    assert 'VIRTUAL_ENV' in os.environ


def bump_version(new_info):
    path = os.path.join('porcupine', '__init__.py')
    with open(path, 'r') as f:
        content = f.read()
    assert repr(old_info) in content

    content = content.replace(repr(old_info), repr(new_info), 1)
    with open(path, 'w') as f:
        f.write(content)

    subprocess.check_call(['git', 'add', path])
    subprocess.check_call(['git', 'commit', '-m', 'v%d.%d.%d' % new_info])
    subprocess.check_call(['git', 'tag', 'v%d.%d.%d' % new_info])
    subprocess.check_call(['git', 'push', 'origin', 'master'])
    subprocess.check_call(['git', 'push', '--tags', 'origin', 'master'])
    subprocess.check_call([sys.executable, 'docs/publish.py'])
    print("Bumped version from %d.%d.%d to %d.%d.%d" % (old_info + new_info))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'what_to_bump', choices=['major', 'minor', 'patch'],
        help="which part of major.minor.patch version number to increment")
    args = parser.parse_args()

    if args.what_to_bump == 'major':
        new_info = (old_info[0]+1, 0, 0)
    elif args.what_to_bump == 'minor':
        new_info = (old_info[0], old_info[1]+1, 0)
    elif args.what_to_bump == 'patch':
        new_info = (old_info[0], old_info[1], old_info[2]+1)
    else:
        assert False, "unexpected what_to_bump %r" % args.what_to_bump

    check_stuff()
    bump_version(new_info)


if __name__ == '__main__':
    main()
