from porcupine import utils


def test_rstrip(filetab):
    filetab.textwidget.insert('end', 'print("hello")  ')
    filetab.update()
    filetab.event_generate('<Return>')
    filetab.update()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'print("hello")\n'

    # ctrl+enter should not wipe trailing whitespace
    filetab.textwidget.delete('1.0', 'end')
    filetab.textwidget.insert('end', 'print("hello")  ')
    filetab.update()
    filetab.event_generate(f'<{utils.contmand()}-Return>')
    filetab.update()
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'print("hello")  \n'
