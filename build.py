import glob
import os
import shutil

from tree_sitter import Language


try:
    shutil.rmtree("build")
except FileNotFoundError:
    pass

os.mkdir("build")
os.system("cd build && git clone --depth=1 https://github.com/tree-sitter/tree-sitter-python")
os.system("cd build && git clone --depth=1 https://github.com/ikatyang/tree-sitter-markdown")

Language.build_library("build/langs.so", glob.glob("build/*"))
print("Created build/langs.so")
