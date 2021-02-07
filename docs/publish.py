#!/usr/bin/env python3
"""build the docs and commit them to the gh-pages branch"""

import functools
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile

info = functools.partial(print, f'**** {sys.argv[0]}:')


def run(*command, cwd=None):
    command_string = ' '.join(map(shlex.quote, command))
    if cwd:
        print(f"running {command_string} in {cwd}")
    else:
        print(f"running {command_string}")

    subprocess.check_call(list(command), cwd=cwd)


def main():
    if os.path.basename(os.getcwd()) == 'docs':
        print("running in docs dir, going up a level")
        os.chdir('..')
    if not os.path.isdir('docs'):
        sys.exit(f"{sys.argv[0]}: docs directory not found")
    if not os.environ.get('VIRTUAL_ENV'):
        sys.exit(f"{sys.argv[0]}: not running in virtualenv (see README.md)")

    info("creating a temporary directory for building docs")
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_docs = pathlib.Path(tmpdir) / 'docs'
        temp_repo = pathlib.Path(tmpdir) / 'repo'

        run(sys.executable, '-m', 'sphinx', 'docs', str(temp_docs))
        run('git', 'clone', '--depth=1', '--branch=gh-pages', 'https://github.com/Akuli/porcupine', str(temp_repo))
        run('git', 'checkout', 'gh-pages', cwd=temp_repo)

        for subpath in temp_repo.iterdir():
            if subpath.name not in {'.git', '.gitignore'}:
                try:
                    shutil.rmtree(subpath)
                except NotADirectoryError:
                    subpath.unlink()

        for subpath in temp_docs.iterdir():
            subpath.rename(temp_repo / subpath.name)

        run('git', 'add', '--all', '.', cwd=temp_repo)
        run('git', 'commit', '-m', f'updating docs with {__file__}', cwd=temp_repo)
        run('git', 'push', 'origin', 'gh-pages', cwd=temp_repo)


if __name__ == '__main__':
    main()
