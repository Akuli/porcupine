import os
import tree_sitter
from zipfile import ZipFile

z = ZipFile("porcupine/plugins/highlight/tree-sitter-data/tree-sitter-binaries.zip")
z.extract("tree-sitter-binary-win32-AMD64.dll")
x = tree_sitter.Language(os.path.abspath("tree-sitter-binary-win32-AMD64.dll"), "python")
