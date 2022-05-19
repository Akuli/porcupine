import os
import shutil
from tree_sitter import Language, Parser


try:
    shutil.rmtree("build")
except FileNotFoundError:
    pass

os.mkdir("build")
os.system("cd build && git clone --depth=1 https://github.com/tree-sitter/tree-sitter-python")

Language.build_library("build/lang-python.so", ['build/tree-sitter-python'])
print("Created build/lang-python.so")
