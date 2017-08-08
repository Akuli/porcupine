#!/usr/bin/env python3
"""build the docs and commit them to the gh-pages branch

this script is crazy, use with caution
"""

import contextlib
import functools
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

info = functools.partial(print, '**** %s:' % sys.argv[0])


def run(*command, capture=False):
    info("running", ' '.join(map(shlex.quote, command)))
    if capture:
        output = subprocess.check_output(list(command))
        return output.decode('utf-8', errors='replace')

    subprocess.check_call(list(command))
    return None     # pep-8


def remove(item):
    info("removing '%s'" % item)
    if os.path.isdir(item):
        shutil.rmtree(item)
    else:
        os.remove(item)


def copy(src, dst):
    info("copying '%s' to '%s'" % (src, dst))
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy(src, dst)


def current_branch():
    output = run('git', 'branch', capture=True)
    [branch] = re.findall('^\* (.*)$', output, flags=re.MULTILINE)
    return branch


@contextlib.contextmanager
def switch_branch(new_branch):
    old_branch = current_branch()
    run('git', 'checkout', new_branch)

    try:
        yield
    except Exception as e:
        # undo everything to make sure the checkout works
        run('git', 'reset', 'HEAD', '.')
        run('git', 'checkout', '--', '.')
    finally:
        run('git', 'checkout', old_branch)


def get_ignored_files():
    yield '.git'
    yield '.gitignore'
    yield 'objects.inv'

    # make this better if you need to
    with open('.gitignore', 'r') as file:
        for line in file:
            yield line.rstrip('\n/')


def main():
    if os.path.dirname(os.getcwd()) == 'docs':
        info("running in docs dir, going up a level")
        os.chdir('..')
    if not os.path.isdir('docs'):
        print("%s: docs directory not found" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    info("creating a temporary directory for building docs")
    with tempfile.TemporaryDirectory() as tmpdir:
        run(sys.executable, '-m', 'sphinx', 'docs', tmpdir)

        with switch_branch('gh-pages'):
            ignored = set(get_ignored_files())
            for item in (set(os.listdir()) - ignored):
                remove(item)
            for item in (set(os.listdir(tmpdir)) - ignored):
                copy(os.path.join(tmpdir, item), item)

            run('git', 'add', '--all', '.')
            run('git', 'commit', '-m', 'updating docs with ' + __file__)

        info("deleting the temporary directory")

    print()
    print('*' * 70)
    print("Done! Now run 'git push origin gh-pages' to upload the "
          "documentation.")


if __name__ == '__main__':
    main()
