import logging
import pickle
import shutil
import sys
from pathlib import Path
from tkinter import filedialog

import pytest

from porcupine import dirs, filedialog_kwargs, get_main_window
from porcupine.plugins import filetypes


@pytest.fixture
def custom_filetypes():
    # We don't overwrite the user's file because porcupine.dirs is monkeypatched
    if sys.platform == "win32":
        assert "\\Temp\\" in dirs.user_config_dir
    else:
        assert not dirs.user_config_dir.startswith(str(Path.home()))

    user_filetypes = Path(dirs.user_config_dir) / "filetypes.toml"
    user_filetypes.write_text(
        """
["Mako template"]
filename_patterns = ["mako-templates/*.html"]
pygments_lexer = 'pygments.lexers.MakoHtmlLexer'

["C++".langserver]
command = "clangd"
language_id = "cpp"
settings = {clangd = {arguments = ["-std=c++17"]}}
"""
    )
    filetypes.filetypes.clear()
    filetypes.load_filetypes()
    filetypes.set_filedialog_kwargs()

    yield
    user_filetypes.unlink()
    filetypes.filetypes.clear()
    filetypes.load_filetypes()
    filetypes.set_filedialog_kwargs()


def test_filedialog_patterns_got_stripped():
    python_patterns = dict(filedialog_kwargs["filetypes"])["Python"]
    assert "*.py" not in python_patterns
    assert ".py" in python_patterns


@pytest.mark.skipif(sys.platform != "linux", reason="don't know how filedialog works on non-Linux")
def test_actually_running_filedialog(custom_filetypes):
    # Wait and then press Esc. That's done as Tcl code because the Tk widget
    # representing the dialog can't be used with tkinter.
    root = get_main_window().nametowidget(".")
    root.after(1000, root.eval, "event generate [focus] <Escape>")

    # If filedialog_kwargs are wrong, then this errors.
    filedialog.askopenfilename(**filedialog_kwargs)


def test_bad_filetype_on_command_line(run_porcupine):
    output = run_porcupine(["-n", "FooBar"], 2)
    assert "no filetype named 'FooBar'" in output


def test_unknown_filetype(filetab, tmp_path):
    # pygments does not know graphviz, see how it gets handled
    filetab.textwidget.insert(
        "end",
        """\
digraph G {
    Hello->World;
}
""",
    )
    filetab.path = tmp_path / "graphviz-hello-world.gvz"
    filetab.save()
    lexer_class_name = filetypes.get_filetype_for_tab(filetab)["pygments_lexer"]
    assert lexer_class_name.endswith(".TextLexer")


def test_slash_in_filename_patterns(custom_filetypes, caplog, tmp_path):
    def lexer_name(path):
        return filetypes.guess_filetype_from_path(path)["pygments_lexer"]

    assert lexer_name(tmp_path / "foo" / "bar.html") == "pygments.lexers.HtmlLexer"
    assert lexer_name(tmp_path / "lol-mako-templates" / "bar.html") == "pygments.lexers.HtmlLexer"
    with caplog.at_level(logging.WARNING):
        assert (
            lexer_name(tmp_path / "mako-templates" / "bar.html") == "pygments.lexers.MakoHtmlLexer"
        )

    assert len(caplog.records) == 1
    assert "2 file types match" in caplog.records[0].message
    assert str(tmp_path) in caplog.records[0].message
    assert "HTML, Mako template" in caplog.records[0].message

    # filedialog doesn't support slashes in patterns
    for filetype_name, patterns in filedialog_kwargs["filetypes"]:
        for pattern in patterns:
            assert "/" not in pattern


@pytest.mark.skipif(shutil.which("clangd") is None, reason="example config uses clangd")
def test_cplusplus_toml_bug(tmp_path, tabmanager, custom_filetypes):
    (tmp_path / "foo.cpp").touch()
    tab = tabmanager.open_file(tmp_path / "foo.cpp")
    pickle.dumps(tab.get_state())  # should not raise an error


def test_settings_reset_when_filetype_changes(filetab, tmp_path):
    assert filetab.settings.get("filetype_name", object) == "Python"
    assert filetab.settings.get("comment_prefix", object) == "#"
    assert filetab.settings.get("langserver", object) is not None
    assert len(filetab.settings.get("example_commands", object)) >= 2

    filetab.save_as(tmp_path / "asdf.css")
    assert filetab.settings.get("filetype_name", object) is None
    assert filetab.settings.get("comment_prefix", object) is None
    assert filetab.settings.get("langserver", object) is None
    assert len(filetab.settings.get("example_commands", object)) == 0


def test_merging_settings():
    default = {
        "Plain Text": {"filename_patterns": ["*.txt"]},
        "Python": {
            "filename_patterns": ["*.py", "*.pyw"],
            "langserver": {
                "command": "{porcupine_python} -m pyls",
                "language_id": "python",
                "settings": {"pyls": {"plugins": {"jedi": {"environment": "{python_venv}"}}}},
            },
        },
    }
    user = {
        "Python": {
            "filename_patterns": ["*.foobar"],
            "langserver": {"settings": {"pyls": {"plugins": {"flake8": {"enabled": True}}}}},
        },
        "Custom File Type": {"filename_patterns": ["*.custom"]},
    }

    assert filetypes.merge_settings(default, user) == {
        "Plain Text": {"filename_patterns": ["*.txt"]},
        "Python": {
            "filename_patterns": ["*.py", "*.pyw", "*.foobar"],
            "langserver": {
                "command": "{porcupine_python} -m pyls",
                "language_id": "python",
                "settings": {
                    "pyls": {
                        "plugins": {
                            "jedi": {"environment": "{python_venv}"},
                            "flake8": {"enabled": True},
                        }
                    }
                },
            },
        },
        "Custom File Type": {"filename_patterns": ["*.custom"]},
    }
