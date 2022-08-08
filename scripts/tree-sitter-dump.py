# Print a tree-sitter syntax tree. Meant to be used for configuring the
# tree-sitter syntax highlighter. Documented in the following file:
#
#    porcupine/plugins/highlight/tree_sitter_data/token_mappings/readme.txt
#
import reprlib
import sys
from pathlib import Path

from tree_sitter import Language, Parser

sys.path.append(str(Path(__file__).absolute().parent.parent))
from porcupine.plugins.highlight.tree_sitter_highlighter import prepare_binary

[program_name, language_name, filename] = sys.argv


def show_nodes(cursor, indent_level=0):
    node = cursor.node
    print(f"{'  ' * indent_level}type={node.type} text={reprlib.repr(node.text.decode('utf-8'))}")

    if cursor.goto_first_child():
        show_nodes(cursor, indent_level + 1)
        while cursor.goto_next_sibling():
            show_nodes(cursor, indent_level + 1)
        cursor.goto_parent()


binary_path = prepare_binary()
assert binary_path is not None

parser = Parser()
parser.set_language(Language(str(binary_path), language_name))
tree = parser.parse(open(filename, "rb").read())
show_nodes(tree.walk())
