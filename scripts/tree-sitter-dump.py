# Print a tree-sitter syntax tree. Meant to be used for configuring the
# tree-sitter syntax highlighter. Documented in the following file:
#
#    porcupine/plugins/highlight/tree_sitter_data/token_mappings/readme.txt
#
import argparse
import reprlib
import sys
from pathlib import Path

from tree_sitter import Parser
from tree_sitter_languages import get_language

sys.path.append(str(Path(__file__).absolute().parent.parent))

parser = argparse.ArgumentParser()
parser.add_argument('language_name')
parser.add_argument('file', type=argparse.FileType('rb'))
parser.add_argument('--query')
args = parser.parse_args()

def print_node(node):
    print(f"type={node.type} text={reprlib.repr(node.text.decode('utf-8'))}")

def show_nodes(cursor, indent_level=0):
    node = cursor.node
    field_name = cursor.current_field_name()
    print("  "*indent_level, end="")
    if field_name is not None:
        print(f"field {field_name!r}:", end=" ")
    print_node(node)

    if cursor.goto_first_child():
        show_nodes(cursor, indent_level + 1)
        while cursor.goto_next_sibling():
            show_nodes(cursor, indent_level + 1)
        cursor.goto_parent()


language = get_language(args.language_name)
parser = Parser()
parser.set_language(language)
tree = parser.parse(args.file.read())
show_nodes(tree.walk())

if args.query:
    print()
    print("Running query on the tree:", args.query)
    matches = language.query(args.query).captures(tree.root_node)
    if matches:
        for node, tag in matches:
            print(f"  @{tag} matched:", end=" ")
            print_node(node)
    else:
        print("  No '@' matches")
