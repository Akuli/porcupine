import platform
import pytest
from tkinter import filedialog

from porcupine import filedialog_kwargs, get_main_window
from porcupine.plugins import filetypes


def test_filedialog_patterns_got_stripped(porcusession):
    python_patterns = dict(filedialog_kwargs['filetypes'])['Python']
    assert '*.py' not in python_patterns
    assert '.py' in python_patterns


@pytest.mark.skipif(
    platform.system() != 'Linux',
    reason="don't know how filedialog works on non-Linux")
def test_actually_running_filedialog():
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
    filetab.textwidget.insert('end', '''\
digraph G {
    Hello->World;
}
''')
    filetab.path = tmp_path / 'graphviz-hello-world.gvz'
    filetab.save()
    lexer_class_name = filetypes.get_filetype_for_tab(filetab)['pygments_lexer']
    assert lexer_class_name.endswith('.TextLexer')
