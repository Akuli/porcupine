#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import subprocess
import sys

from porcupine import version_info as old_info


def edit_init_dot_py(new_info):
    with open('porcupine/__init__.py', 'r') as f:
        content = f.read()

    assert repr(old_info) in content
    content = content.replace(repr(old_info), repr(new_info), 1)

    with open('porcupine/__init__.py', 'w') as f:
        f.write(content)


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

    status = subprocess.check_output(['git', 'status'])
    assert status.startswith(b'On branch master\n')
    assert b'Changes not staged for commit:' not in status
    assert 'VIRTUAL_ENV' in os.environ

    print("Bumping version from %d.%d.%d to %d.%d.%d" % (old_info + new_info))

    edit_init_dot_py(new_info)
    subprocess.check_call(['git', 'add', 'porcupine/__init__.py'])
    subprocess.check_call(['git', 'commit', '-m', 'v%d.%d.%d' % new_info])
    subprocess.check_call(['git', 'tag', 'v%d.%d.%d' % new_info])
    subprocess.check_call(['git', 'push', 'origin', 'master'])
    subprocess.check_call(['git', 'push', '--tags', 'origin', 'master'])
    subprocess.check_call([sys.executable, 'docs/publish.py'])


if __name__ == '__main__':
    main()
