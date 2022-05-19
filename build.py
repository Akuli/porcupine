import glob
import os
import shutil
import subprocess

from tree_sitter import Language


repos = [
    "https://github.com/ikatyang/tree-sitter-markdown",
    "https://github.com/ikatyang/tree-sitter-toml",
    "https://github.com/tree-sitter/tree-sitter-agda",
    "https://github.com/tree-sitter/tree-sitter-bash",
    "https://github.com/tree-sitter/tree-sitter-c",
    "https://github.com/tree-sitter/tree-sitter-c-sharp",
    "https://github.com/tree-sitter/tree-sitter-cpp",
    "https://github.com/tree-sitter/tree-sitter-embedded-template",
    "https://github.com/tree-sitter/tree-sitter-fluent",
    "https://github.com/tree-sitter/tree-sitter-go",
    "https://github.com/tree-sitter/tree-sitter-haskell",
    "https://github.com/tree-sitter/tree-sitter-html",
    "https://github.com/tree-sitter/tree-sitter-java",
    "https://github.com/tree-sitter/tree-sitter-javascript",
    "https://github.com/tree-sitter/tree-sitter-json",
    "https://github.com/tree-sitter/tree-sitter-julia",
    "https://github.com/tree-sitter/tree-sitter-php",
    "https://github.com/tree-sitter/tree-sitter-python",
    "https://github.com/tree-sitter/tree-sitter-ruby",
    "https://github.com/tree-sitter/tree-sitter-rust",
    "https://github.com/tree-sitter/tree-sitter-scala",
    "https://github.com/tree-sitter/tree-sitter-swift",
]

try:
    shutil.rmtree("build")
except FileNotFoundError:
    pass

os.mkdir("build")
for repo in repos:
    subprocess.check_call(["git", "clone", "--depth=1", repo], cwd="build")

Language.build_library("build/langs.so", glob.glob("build/*"))
print("Created build/langs.so")
