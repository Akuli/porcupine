"""
One of Porcupine's two syntax highlighter plugins uses py-tree-sitter.
py-tree-sitter wants to use a C compiler to build language definitions.
This is great, because it makes py-tree-sitter fast, except that most Porcupine users don't have a C compiler.

This script does all things that need C compiler.
It produces a platform-specific binary file.
Use GitHub Actions to easily run this script on Windows, MacOS and Linux.
"""
# TODO: create the github action and update instructions here
import platform
import shutil
import sys
import subprocess
from pathlib import Path

from tree_sitter import Language


Path("build").mkdir(exist_ok=True)

syntax_dirs = []
with Path(__file__).absolute().with_name("tree-sitter-syntax-repos.txt").open() as file:
    for line in file:
        repo, commit = line.split()
        target_dir = Path("build") / repo.split("/")[-1]

        if not target_dir.is_dir():
            print(f"Cloning: {repo} --> {target_dir}")
            subprocess.check_call(["git", "clone", "-q", "--depth=1", repo, target_dir])

        print(f"Checking out commit {commit} in {target_dir}")
        try:
            subprocess.check_call(["git", "checkout", "-q", commit], cwd=target_dir)
        except subprocess.CalledProcessError:
            subprocess.check_call(["git", "fetch", "-q"], cwd=target_dir)
            subprocess.check_call(["git", "checkout", "-q", commit], cwd=target_dir)

        syntax_dirs.append(target_dir)

extension = {"win32": ".dll", "darwin": ".dylib", "linux": ".so"}[sys.platform]
binary_filename = f"syntax-binary-{sys.platform}-{platform.machine()}{extension}"
print("Building", binary_filename)

# Build to a temporary file first, because otherwise we end up with three files for some reason:
#
#   syntax-binary-win32-x86_64.dll    <-- this is the only file we need
#   syntax-binary-win32-x86_64.exp
#   syntax-binary-win32-x86_64.lib
Language.build_library("build/out" + extension, syntax_dirs)
shutil.copy("build/out" + extension, binary_filename)
