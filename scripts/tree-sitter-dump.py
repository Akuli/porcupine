# Print a tree-sitter syntax tree. Meant to be used for configuring the
# tree-sitter syntax highlighter. Documented in the following file:
#
#    porcupine/plugins/highlight/tree_sitter_data/token_mappings/readme.txt
#
import reprlib
import sys
from pathlib import Path

from tree_sitter_languages import get_parser

sys.path.append(str(Path(__file__).absolute().parent.parent))

[program_name, language_name, filename] = sys.argv


def show_nodes(cursor, indent_level=0):
    node = cursor.node
    field_name = cursor.current_field_name()
    print("  "*indent_level, end="")
    if field_name is not None:
        print(f"field {field_name!r}:", end=" ")
    print(f"type={node.type} text={reprlib.repr(node.text.decode('utf-8'))}")

    if cursor.goto_first_child():
        show_nodes(cursor, indent_level + 1)
        while cursor.goto_next_sibling():
            show_nodes(cursor, indent_level + 1)
        cursor.goto_parent()


parser = get_parser(language_name)
tree = parser.parse(open(filename, "rb").read())
show_nodes(tree.walk())
