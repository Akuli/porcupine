# not much can be done here, other than running the dialog and trying to get a
# good coverage

from urllib.request import url2pathname

from porcupine.plugins import aboutdialog


def test_it_doesnt_crash(monkeypatch, monkeypatch_dirs):
    called = 0

    def fake_wait_window(self):
        nonlocal called
        called += 1
        self.destroy()  # can't do this with mock objects

    monkeypatch.setattr("tkinter.Toplevel.wait_window", fake_wait_window)
    get_main_window().event_generate("<<Menubar:Help/About Porcupine>>")
    assert called == 1


def test_show_huge_logo(mocker):
    mock = mocker.patch("porcupine.plugins.aboutdialog.webbrowser").open
    aboutdialog.show_huge_logo()
    mock.assert_called_once()

    [url] = mock.call_args[0]
    assert url.startswith("file://")
    path = url2pathname(url[len("file://") :])

    assert path.endswith(".gif")
    with open(path, "rb") as file:
        assert file.read(3) == b"GIF"
