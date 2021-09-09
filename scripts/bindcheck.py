#!/usr/bin/env python3
"""Check for common bind-related errors. See docs/plugin-intro for explanation."""

import ast
import sys
from pathlib import Path

program_name, code_dir = sys.argv
paths = list(Path(code_dir).rglob("*.py"))


def is_method_call(node, names):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in names
    )


missing_add = {
    (path, node.lineno)
    for path in paths
    for node in ast.walk(ast.parse(path.read_text()))
    # add=True not required for tag_bind, because those typically bind a freshly
    # created tag with no other bindings that would accidentally go away
    if is_method_call(node, {"bind", "bind_all", "bind_class", "bind_with_data"})
    and "add" not in (kw.arg for kw in node.keywords)
    and len(node.args) >= 2  # widget.bind(one_argument) doesn't need add=True
}
tag_bind_in_loop = {
    (path, body_node.lineno)
    for path in paths
    for loop_node in ast.walk(ast.parse(path.read_text()))
    for body_node in (ast.walk(loop_node) if isinstance(loop_node, (ast.For, ast.While)) else [])
    if is_method_call(body_node, {"tag_bind"})
    # allow appending bindings to a list of commands to clean up
    and ".append(" not in path.read_text().splitlines()[body_node.lineno - 1]
}
ignores = {
    (path, lineno)
    for path in paths
    for lineno, line in enumerate(path.read_text().splitlines(), start=1)
    if "# bindcheck: ignore" in line
}

messages = (
    [f"  {path}:{lineno}: missing add=True" for path, lineno in sorted(missing_add - ignores)]
    + [
        f"  {path}:{lineno}: tag_bind() in loop without .append()"
        for path, lineno in sorted(tag_bind_in_loop - ignores)
    ]
    + [
        f"  {path}:{lineno}: unused ignore comment"
        for path, lineno in sorted(ignores - (missing_add | tag_bind_in_loop))
    ]
)

if messages:
    print("bind errors:")
    print("\n".join(messages))
    sys.exit(1)
