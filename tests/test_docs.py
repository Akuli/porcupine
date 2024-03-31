import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from porcupine import menubar


# plugin-structure.md contains a small but complete plugin that adds a --foo command line option.
# Let's test it.
def test_plugin_structure_md_example_plugin(tmp_path):
    shutil.copytree("porcupine", tmp_path / "porcupine")
    match = re.search(
        r"```python\n([^`]+def setup_argument_parser[^`]+)\n```",
        Path("dev-doc/plugin-structure.md").read_text(),
    )
    (tmp_path / "porcupine" / "plugins" / "foo.py").write_text(match.group(1))
    output = subprocess.check_output(
        [sys.executable, "-m", "porcupine", "--help"], cwd=tmp_path, text=True
    )
    assert "--foo shows message box" in re.sub(r" +", " ", output)


# Docstring of menubar.py also contains an example plugin.
# Let's run its setup() function and make sure it did the right thing.
def test_menubar_docstring_example_plugin(mocker):
    code = re.search(r"\n    .*\n(    .*\n|\n)+", menubar.__doc__).group(0)
    namespace = {}
    exec(textwrap.dedent(code), namespace)
    namespace["setup"]()

    mock = mocker.patch("tkinter.messagebox.showinfo")
    menubar.get_menu("Run/Greetings").invoke("Hello World")
    mock.assert_called_once_with("Hello", "Hello World!")
