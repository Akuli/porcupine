import platform
import pytest
from tkinter import filedialog

from porcupine import filedialog_kwargs, get_main_window


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
