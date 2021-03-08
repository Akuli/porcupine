def test_comment_block_and_undo(filetab, tmp_path):
    filetab.save_as(tmp_path / "hello.py")
    filetab.textwidget.insert('1.0', 'foo\nbar\nbaz')
    filetab.textwidget.tag_add('sel', '1.0', 'end - 1 char')
    filetab.textwidget.event_generate('<numbersign>')   # hashtag key press
    filetab.textwidget.insert('end - 1 char', 'lol')

    # Don't know why a trailing newline appears, but it doesn't matter much
    assert filetab.textwidget.get('1.0', 'end - 1 char') == '#foo\n#bar\n#baz\nlol'
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == '#foo\n#bar\n#baz\n'
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'foo\nbar\nbaz\n'
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == ''
