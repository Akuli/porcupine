# see .github/workflows/tree-sitter-binaries.yml
import os
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
binary_filename = f"tree-sitter-binary-{sys.platform}-{platform.machine()}{extension}"
print("Building", binary_filename)

# Build to a temporary file first, because for some reason we end up with three files on windows:
#
#   tree-sitter-binary-win32-AMD64.dll    <-- this is the only file we need
#   tree-sitter-binary-win32-AMD64.exp
#   tree-sitter-binary-win32-AMD64.lib
#
# Other files will stay in build.
Language.build_library("build/" + binary_filename, syntax_dirs)
shutil.copy("build/" + binary_filename, binary_filename)

# Sanity check: can we load a language from the new binary?
Language(os.path.abspath(binary_filename), "python")
