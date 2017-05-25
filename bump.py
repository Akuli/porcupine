#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import argparse
import os
import subprocess

from porcupine import version_info as old_info


def bump_init(new_info):
    path = os.path.join('porcupine', '__init__.py')
    with open(path, 'r') as f:
        content = f.read()
    assert repr(old_info) in content

    content = content.replace(repr(old_info), repr(new_info), 1)
    with open(path, 'w') as f:
        f.write(content)


def bump_git_tag(new_version):
    subprocess.call('git', 'tag', 'v%d.%d.%d' % new_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('what-to-bump', choices=['major', 'minor', 'patch'])
    args = parser.parse_args()

    # argparse fails to translate - to _ :(
    what_to_bump = getattr(args, 'what-to-bump')
    if what_to_bump == 'major':
        new_info = (old_info[0]+1, 0, 0)
    elif what_to_bump == 'minor':
        new_info = (old_info[0], old_info[1]+1, 0)
    elif what_to_bump == 'patch':
        new_info = (old_info[0], old_info[1], old_info[2]+1)
    else:
        assert False, "something weird happened"

    bump_init(new_info)
    bump_git_tag(new_info)
    print("Bumped version from %d.%d.%d to %d.%d.%d" % (old_info + new_info))


if __name__ == '__main__':
    main()
