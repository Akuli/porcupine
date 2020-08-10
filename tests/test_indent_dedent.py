_FUNNY = '''\
def foo(
    x,
     y
'''
_DEDENTED = '''\
def foo(
    x,
    y
'''
_BEFORE_Y = '3.5'
_AFTER_Y = '3.6'


# issue 65
def test_dedent_when_misaligned(filetab):
    filetab.settings.set('indent_size', 4)
    filetab.settings.set('tabs2spaces', True)
    filetab.update()

    filetab.textwidget.insert('end', _FUNNY)
    assert filetab.textwidget.dedent(_BEFORE_Y)
    assert filetab.textwidget.get('1.0', 'end - 1 char') == _DEDENTED


# issue 74
def test_doesnt_delete_stuff_far_away_from_cursor(filetab):
    filetab.settings.set('indent_size', 4)
    filetab.settings.set('tabs2spaces', True)
    filetab.update()

    filetab.textwidget.insert('end', _FUNNY)
    assert not filetab.textwidget.dedent(_AFTER_Y)
    assert filetab.textwidget.get('1.0', 'end - 1 char') == _FUNNY
