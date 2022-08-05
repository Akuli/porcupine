"""
One of Porcupine's two syntax highlighter plugins uses py-tree-sitter.
py-tree-sitter wants to use a C compiler to build language definitions.
This is great, because it makes py-tree-sitter fast, except that most Porcupine users don't have a C compiler.

This script does all things that need C compiler.
It produces a platform-specific binary file.
Use GitHub Actions to easily run this script on Windows, MacOS and Linux.
"""
# TODO: create the github action and update instructions here
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
            subprocess.check_call(["git", "clone", "--depth=1", repo, target_dir])

        print(f"Checking out commit {commit} in {target_dir}")
        try:
            subprocess.check_call(["git", "checkout", commit], cwd=target_dir)
        except subprocess.CalledProcessError:
            subprocess.check_call(["git", "fetch"], cwd=target_dir)
            subprocess.check_call(["git", "checkout", commit], cwd=target_dir)

        syntax_dirs.append(target_dir)

if sys.platform == "win32":
    binary_filename = "syntax-binary-windows.dll"  # TODO: verify if it is a dll file or something else
elif sys.platform == "darwin":
    binary_filename = "syntax-binary-macos.so"
elif sys.platform == "linux":
    binary_filename = "syntax-binary-linux.so"
else:
    raise RuntimeError("unsupported platform: " + sys.platform)

print("Building", binary_filename)
Language.build_library(binary_filename, syntax_dirs)
