import dataclasses
import platform
import typing
from tkinter import ttk

from porcupine import get_main_window, utils


def test_bind_with_data_string():
    # i don't know why the main window works better with this than a
    # temporary tkinter.Frame()
    events = []
    utils.bind_with_data(get_main_window(), '<<Asd>>', events.append, add=True)
    get_main_window().event_generate('<<Asd>>', data='hello')

    [event] = events
    assert event.widget is get_main_window()
    assert event.data_string == 'hello'


@dataclasses.dataclass
class Foo:
    message: str
    num: int


@dataclasses.dataclass
class Bar(utils.EventDataclass):
    foos: typing.List[Foo]


def test_bind_with_data_class():
    events = []
    utils.bind_with_data(
        get_main_window(), '<<DataclassAsd>>', events.append, add=True)
    get_main_window().event_generate(
        '<<DataclassAsd>>', data=Bar(foos=[Foo(message='abc', num=123)]))

    [event] = events
    bar = event.data_class(Bar)
    [foo] = bar.foos
    assert foo.message == 'abc'
    assert foo.num == 123


def test_get_children_recursively():
    parent = ttk.Frame()
    try:
        child1 = ttk.Button(parent)
        child2 = ttk.Frame(parent)
        child2a = ttk.Progressbar(child2)
        child2b = ttk.Sizegrip(child2)

        assert list(utils.get_children_recursively(parent)) == [child1, child2, child2a, child2b]
        assert list(utils.get_children_recursively(parent, include_parent=True)) == [
            parent, child1, child2, child2a, child2b]
    finally:
        parent.destroy()


def test_get_keyboard_shortcut():
    if platform.system() == 'Darwin':
        # Tk will show these with the proper symbols and stuff when these go to menu
        assert utils.get_keyboard_shortcut('<Command-n>', menu=True) == 'Command-N'
        assert utils.get_keyboard_shortcut('<Mod1-Key-n>', menu=True) == 'Command-N'
        assert utils.get_keyboard_shortcut('<Command-s>', menu=True) == 'Command-S'
        assert utils.get_keyboard_shortcut('<Command-S>', menu=True) == 'Command-Shift-S'
        assert utils.get_keyboard_shortcut('<Command-plus>', menu=True) == 'Command-+'
        assert utils.get_keyboard_shortcut('<Command-minus>', menu=True) == 'Command--'
        assert utils.get_keyboard_shortcut('<Command-0>', menu=True) == 'Command-0'
        assert utils.get_keyboard_shortcut('<Command-1>', menu=True) == 'Command-1'
        assert utils.get_keyboard_shortcut('<Alt-f>', menu=True) == 'Alt-F'
        assert utils.get_keyboard_shortcut('<F4>', menu=True) == 'F4'
        assert utils.get_keyboard_shortcut('<F11>', menu=True) == 'F11'

        assert utils.get_keyboard_shortcut('<Command-n>', menu=False) == '⌘N'
        assert utils.get_keyboard_shortcut('<Mod1-Key-n>', menu=False) == '⌘N'
        assert utils.get_keyboard_shortcut('<Command-s>', menu=False) == '⌘S'
        assert utils.get_keyboard_shortcut('<Command-S>', menu=False) == '⇧⌘S'
        assert utils.get_keyboard_shortcut('<Command-plus>', menu=False) == '⌘+'
        assert utils.get_keyboard_shortcut('<Command-minus>', menu=False) == '⌘-'
        assert utils.get_keyboard_shortcut('<Command-0>', menu=False) == '⌘0'
        assert utils.get_keyboard_shortcut('<Command-1>', menu=False) == '⌘1'
        assert utils.get_keyboard_shortcut('<Alt-f>', menu=False) == '⌥F'
        assert utils.get_keyboard_shortcut('<F4>', menu=False) == 'F4'
        assert utils.get_keyboard_shortcut('<F11>', menu=False) == 'F11'

    else:
        # menu option has no effect
        for boolean in [True, False]:
            assert utils.get_keyboard_shortcut('<Control-c>', menu=boolean) == 'Ctrl+C'
            assert utils.get_keyboard_shortcut('<Control-Key-c>', menu=boolean) == 'Ctrl+C'
            assert utils.get_keyboard_shortcut('<Control-C>', menu=boolean) == 'Ctrl+Shift+C'
            assert utils.get_keyboard_shortcut('<Control-plus>', menu=boolean) == 'Ctrl+Plus'
            assert utils.get_keyboard_shortcut('<Control-minus>', menu=boolean) == 'Ctrl+Minus'
            assert utils.get_keyboard_shortcut('<Control-0>', menu=boolean) == 'Ctrl+Zero'
            assert utils.get_keyboard_shortcut('<Control-1>', menu=boolean) == 'Ctrl+1'
            assert utils.get_keyboard_shortcut('<Alt-f>', menu=boolean) == 'Alt+F'
            assert utils.get_keyboard_shortcut('<F4>', menu=boolean) == 'F4'
            assert utils.get_keyboard_shortcut('<F11>', menu=boolean) == 'F11'
