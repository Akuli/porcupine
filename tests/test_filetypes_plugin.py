import logging
import pathlib
import sys
from tkinter import filedialog

import pytest

from porcupine import dirs, filedialog_kwargs, get_main_window
from porcupine.plugins import filetypes


@pytest.fixture
def custom_filetypes():
    # We don't overwrite the user's file because porcupine.dirs is monkeypatched
    assert not dirs.user_config_dir.startswith(str(pathlib.Path.home()))
    user_filetypes = pathlib.Path(dirs.user_config_dir) / 'filetypes.toml'

    user_filetypes.write_text(
        """
['Mako template']
filename_patterns = ["mako-templates/*.html"]
pygments_lexer = 'pygments.lexers.MakoHtmlLexer'
"""
    )
    filetypes.load_filetypes()
    filetypes.set_filedialog_kwargs()

    yield
    user_filetypes.unlink()
    filetypes.filetypes.clear()
    filetypes.load_filetypes()
    filetypes.set_filedialog_kwargs()


def test_filedialog_patterns_got_stripped():
    python_patterns = dict(filedialog_kwargs['filetypes'])['Python']
    assert '*.py' not in python_patterns
    assert '.py' in python_patterns


@pytest.mark.skipif(sys.platform != 'linux', reason="don't know how filedialog works on non-Linux")
def test_actually_running_filedialog(custom_filetypes):
    # Wait and then press Esc. That's done as Tcl code because the Tk widget
    # representing the dialog can't be used with tkinter.
    root = get_main_window().nametowidget('.')
    root.after(1000, root.eval, "event generate [focus] <Escape>")

    # If filedialog_kwargs are wrong, then this errors.
    filedialog.askopenfilename(**filedialog_kwargs)


def test_bad_filetype_on_command_line(run_porcupine):
    output = run_porcupine(['-n', 'FooBar'], 2)
    assert "no filetype named 'FooBar'" in output


def test_unknown_filetype(filetab, tmp_path):
    # pygments does not know graphviz, see how it gets handled
    filetab.textwidget.insert(
        'end',
        '''\
digraph G {
    Hello->World;
}
''',
    )
    filetab.path = tmp_path / 'graphviz-hello-world.gvz'
    filetab.save()
    lexer_class_name = filetypes.get_filetype_for_tab(filetab)['pygments_lexer']
    assert lexer_class_name.endswith('.TextLexer')


def test_slash_in_filename_patterns(custom_filetypes, caplog, tmp_path):
    assert (
        filetypes.guess_filetype_from_path(tmp_path / "foo" / "bar.html")['pygments_lexer']
        == 'pygments.lexers.HtmlLexer'
    )

    assert (
        filetypes.guess_filetype_from_path(tmp_path / "foobar-mako-templates" / "bar.html")[
            'pygments_lexer'
        ]
        == 'pygments.lexers.HtmlLexer'
    )

    with caplog.at_level(logging.WARNING):
        assert (
            filetypes.guess_filetype_from_path(tmp_path / "mako-templates" / "bar.html")[
                'pygments_lexer'
            ]
            == 'pygments.lexers.MakoHtmlLexer'
        )

    assert len(caplog.records) == 1
    assert "2 file types match" in caplog.records[0].message
    assert str(tmp_path) in caplog.records[0].message
    assert "HTML, Mako template" in caplog.records[0].message

    # filedialog doesn't support slashes in patterns
    for filetype_name, patterns in filedialog_kwargs['filetypes']:
        for pattern in patterns:
            assert "/" not in pattern
