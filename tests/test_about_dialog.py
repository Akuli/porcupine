# not much can be done here, other than running the dialog and trying to get a
# good coverage

import os
import tkinter
import types
from urllib.request import url2pathname

from porcupine import actions
from porcupine.plugins import aboutdialog


def test_it_doesnt_crash(monkeypatch, porcusession):
    # the dialog calls .wait_window(), but that doesn't terminate until the
    # user closes the window... so we'll make the window close itself
    called = [0]       # not sure if nonlocal could be used instead

    class FakeToplevel(tkinter.Toplevel):
        def wait_window(self):
            called[0] += 1
            self.destroy()

    fake_tkinter = types.SimpleNamespace()
    fake_tkinter.__dict__.update(tkinter.__dict__)
    fake_tkinter.Toplevel = FakeToplevel

    monkeypatch.setattr(aboutdialog, 'tkinter', fake_tkinter)

    assert actions.get_action('Help/About Porcupine...').enabled
    actions.get_action('Help/About Porcupine...').callback()
    assert called == [1]


def test_show_huge_logo(monkeypatch):
    opened = []
    fake_webbrowser = types.SimpleNamespace(open=opened.append)
    monkeypatch.setattr(aboutdialog, 'webbrowser', fake_webbrowser)
    aboutdialog.show_huge_logo()

    [url] = opened
    assert url.startswith('file://')
    path = url2pathname(url[len('file://'):])
    assert os.path.exists(path)

    # make sure it's a gif
    assert path.endswith('.gif')
    with open(path, 'rb') as file:
        assert file.read(3) == b'GIF'      # every gif file starts with this
