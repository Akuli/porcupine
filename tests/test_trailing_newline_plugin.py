def test_trailing_newline(filetab, tmp_path):
    filetab.path = tmp_path / 'foo.py'
    filetab.textwidget.insert('1.0', 'hello')
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'hello'

    filetab.save()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'hello\n'
    assert (tmp_path / 'foo.py').read_text() == 'hello\n'

    filetab.save()
    filetab.save()
    filetab.save()
    filetab.save()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'hello\n'
    assert (tmp_path / 'foo.py').read_text() == 'hello\n'
