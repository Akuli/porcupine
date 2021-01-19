import pytest

from porcupine import get_main_window

code = '''\
with open(path) as f:
    while True:
        try:
            line = f.readline().decode('utf-8')
        except OSError:
            break

        print(repr(line))
    print("foo")
'''

except_folded = '''\
with open(path) as f:
    while True:
        try:
            line = f.readline().decode('utf-8')
        except OSError:

        print(repr(line))
    print("foo")
'''

while_folded = '''\
with open(path) as f:
    while True:
    print("foo")
'''


# tkinter doesn't support -displaychars option of Text.get
def get_content(textwidget, include_elided):
    if include_elided:
        return textwidget.tk.eval(f'{textwidget} get 1.0 "end - 1 char"')
    else:
        return textwidget.tk.eval(f'{textwidget} get -displaychars 1.0 "end - 1 char"')


@pytest.fixture
def text(filetab):
    text = filetab.textwidget
    text.insert('1.0', code)
    return text


def test_outermost(text):
    text.mark_set('insert', '1.0')
    get_main_window().event_generate('<<Menubar:Edit/Fold>>')
    assert get_content(text, True) == code
    assert get_content(text, False) == 'with open(path) as f:\n'


def test_inner(text):
    text.mark_set('insert', '2.0')
    get_main_window().event_generate('<<Menubar:Edit/Fold>>')
    assert get_content(text, True) == code
    assert get_content(text, False) == while_folded


def test_leaving_blank_lines_behind(text):
    text.mark_set('insert', '5.0')
    get_main_window().event_generate('<<Menubar:Edit/Fold>>')
    assert get_content(text, True) == code
    assert get_content(text, False) == except_folded
