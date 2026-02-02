# There's more langserver related tests in other files, e.g. test_jump_to_definition.py
import sys
from pathlib import Path

from porcupine.plugins.langserver import _file_url_to_path


def test_file_url_to_path():
    if sys.platform == "win32":
        paths = [Path(r"\\Server\Share\Test\Foo Bar.txt"), Path(r"C:\Users\Akuli\Foo Bar.txt")]
    else:
        paths = [Path("/home/akuli/Foo Bar.txt")]

    for path in paths:
        assert _file_url_to_path(path.as_uri()) == path
