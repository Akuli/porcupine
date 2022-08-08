import os
import tempfile
import tree_sitter
from zipfile import ZipFile

z = ZipFile("porcupine/plugins/highlight/tree-sitter-data/tree-sitter-binaries.zip")
with tempfile.TemporaryDirectory() as d:
    z.extract("tree-sitter-binary-win32-AMD64.dll", d)
    x = tree_sitter.Language(os.path.join(d, "tree-sitter-binary-win32-AMD64.dll"), "python")
