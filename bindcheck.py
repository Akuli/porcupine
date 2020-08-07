#!/usr/bin/env python3
"""
Check that every bind call has add=True, add=False or '# bindcheck: ignore'
comment on the same line.
"""

import ast
import pathlib
import sys

program_name, code_dir = sys.argv
paths_and_codes = (
    (path, path.read_text())
    for path in pathlib.Path(code_dir).rglob('*.py')
)
bad_binds = [
    f'  {path}:{node.lineno}'
    for path, code in paths_and_codes
    for node in ast.walk(ast.parse(code))
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute)
    and node.func.attr in {'bind', 'bind_all', 'bind_class', 'bind_with_data'}
    and not any(kw.arg == 'add' for kw in node.keywords)
    and '# bindcheck: ignore' not in code.splitlines()[node.lineno - 1]
]

if bad_binds:
    print("bad binds found:")
    print('\n'.join(bad_binds))
    sys.exit(1)
