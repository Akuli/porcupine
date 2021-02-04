from porcupine.plugins.statusbar import StatusBar


def test_reload_warning(filetab, tmp_path):
    [statusbar] = [w for w in filetab.bottom_frame.winfo_children() if isinstance(w, StatusBar)]

    filetab.path = tmp_path / "lol.py"
    filetab.save()

    filetab.path.write_text("hello")
    filetab.reload()
    filetab.update()
    assert statusbar.left_label['text'].endswith('lol.py')
    assert statusbar.left_label['foreground'] == ''

    filetab.textwidget.insert('1.0', 'asdf')
    filetab.path.write_text("foo")
    filetab.reload()
    filetab.update()
    assert 'Press Ctrl+Z to get your changes back' in statusbar.left_label['text']
    assert statusbar.left_label['foreground'] != ''

    filetab.textwidget.insert('1.0', 'a')   # assumeuser doesn't want changes back
    assert statusbar.left_label['text'].endswith('lol.py')
    assert statusbar.left_label['foreground'] == ''
