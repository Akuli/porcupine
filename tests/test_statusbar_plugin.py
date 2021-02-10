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
    # Ctrl+Z or Command+Z
    assert 'Press ' in statusbar.left_label['text']
    assert 'Z to get your changes back' in statusbar.left_label['text']
    assert statusbar.left_label['foreground'] != ''

    filetab.textwidget.insert('1.0', 'a')   # assume user doesn't want changes back
    assert statusbar.left_label['text'].endswith('lol.py')
    assert statusbar.left_label['foreground'] == ''


def test_selection(filetab):
    [statusbar] = [w for w in filetab.bottom_frame.winfo_children() if isinstance(w, StatusBar)]

    filetab.textwidget.insert('1.0', 'blah\n' * 4)
    filetab.textwidget.mark_set('insert', '1.2')
    assert statusbar.right_label['text'] == 'Line 1, column 2'

    filetab.textwidget.tag_add('sel', '1.2', '1.4')
    filetab.update()
    assert statusbar.right_label['text'] == '2 characters selected'

    filetab.textwidget.tag_add('sel', '1.2', '2.2')
    filetab.update()
    assert statusbar.right_label['text'] == '5 characters on 2 lines selected'

    filetab.textwidget.tag_add('sel', '1.2', '2.4')
    filetab.update()
    assert statusbar.right_label['text'] == '7 characters on 2 lines selected'

    # selecting to end of line doesn't mean next line (consistent with indent_block plugin)
    filetab.textwidget.tag_add('sel', '1.2', '3.0')
    filetab.update()
    assert statusbar.right_label['text'] == '8 characters on 2 lines selected'

    filetab.textwidget.tag_add('sel', '1.2', '3.1')
    filetab.update()
    assert statusbar.right_label['text'] == '9 characters on 3 lines selected'

    filetab.textwidget.tag_remove('sel', '1.0', 'end')
    filetab.update()
    assert statusbar.right_label['text'] == 'Line 1, column 2'
