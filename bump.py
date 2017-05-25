#!/usr/bin/env python3
"""Bump the Porcupine version number."""

import os
import subprocess
import sys

from porcupine import version_info as old_info


def bump_version(new_info):
    path = os.path.join('porcupine', '__init__.py')
    with open(path, 'r') as f:
        content = f.read()
    assert repr(old_info) in content

    content = content.replace(repr(old_info), repr(new_info), 1)
    with open(path, 'w') as f:
        f.write(content)

    subprocess.call(['git', 'add', path])
    subprocess.call(['git', 'commit', '-m', 'bump version'])
    subprocess.call(['git', 'tag', 'v%d.%d.%d' % new_info])
    print("Bumped version from %d.%d.%d to %d.%d.%d" % (old_info + new_info))


def main():
    if sys.argv[1:] == ['major']:
        new_info = (old_info[0]+1, 0, 0)
    elif sys.argv[1:] == ['minor']:
        new_info = (old_info[0], old_info[1]+1, 0)
    elif sys.argv[1:] == ['patch']:
        new_info = (old_info[0], old_info[1], old_info[2]+1)
    else:
        print("Usage:", sys.argv[0], "{major,minor,patch}", file=sys.stderr)
        sys.exit(2)
    bump_version(new_info)


if __name__ == '__main__':
    main()
