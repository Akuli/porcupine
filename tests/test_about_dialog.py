# not much can be done here, other than running the dialog and trying to get a
# good coverage

import tkinter
import types
from urllib.request import url2pathname

from porcupine import get_main_window
from porcupine.plugins import aboutdialog


def test_it_doesnt_crash(monkeypatch):
    # the dialog calls .wait_window(), but that doesn't terminate until the
    # user closes the window... so we'll make the window close itself
    called = 0

    def fake_wait_window(self):
        nonlocal called
        called += 1
        self.destroy()

    monkeypatch.setattr(tkinter.Toplevel, "wait_window", fake_wait_window)

    get_main_window().event_generate("<<Menubar:Help/About Porcupine>>")
    assert called == 1


def test_show_huge_logo(monkeypatch):
    opened = []
    fake_webbrowser = types.SimpleNamespace(open=opened.append)
    monkeypatch.setattr(aboutdialog, "webbrowser", fake_webbrowser)
    aboutdialog.show_huge_logo()

    [url] = opened
    assert url.startswith("file://")
    path = url2pathname(url[len("file://") :])

    # make sure it's a gif
    assert path.endswith(".gif")
    with open(path, "rb") as file:
        assert file.read(3) == b"GIF"  # every gif file starts with this
