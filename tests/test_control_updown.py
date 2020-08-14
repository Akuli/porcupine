bla_bla_bla = '''\
bla

    bla

bla'''


def test_control_down(filetab):
    filetab.textwidget.focus_force()
    filetab.textwidget.insert('1.0', bla_bla_bla)
    filetab.textwidget.mark_set('insert', '1.0')
    assert filetab.textwidget.index('insert') == '1.0'

    filetab.textwidget.event_generate('<Control-Down>')
    assert filetab.textwidget.index('insert') == '3.0'
    filetab.textwidget.event_generate('<Control-Down>')
    assert filetab.textwidget.index('insert') == '5.0'
    filetab.textwidget.event_generate('<Control-Down>')
    assert filetab.textwidget.index('insert') == '5.3'
    filetab.textwidget.event_generate('<Control-Down>')
    assert filetab.textwidget.index('insert') == '5.3'


def test_control_up(filetab):
    filetab.textwidget.focus_force()
    filetab.textwidget.insert('1.0', bla_bla_bla)
    filetab.textwidget.mark_set('insert', 'end')
    assert filetab.textwidget.index('insert') == '5.3'

    filetab.textwidget.event_generate('<Control-Up>')
    assert filetab.textwidget.index('insert') == '3.0'
    filetab.textwidget.event_generate('<Control-Up>')
    assert filetab.textwidget.index('insert') == '1.0'
    filetab.textwidget.event_generate('<Control-Up>')
    assert filetab.textwidget.index('insert') == '1.0'
