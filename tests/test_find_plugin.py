# TODO: test overlapping matches
import contextlib
import itertools
import random
from tkinter import ttk

import pytest

from porcupine import actions, get_tab_manager, tabs
from porcupine.plugins import find


@pytest.fixture
def filetab(porcusession, tabmanager):
    tab = tabs.FileTab(get_tab_manager())
    get_tab_manager().add_tab(tab)
    yield tab
    get_tab_manager().close_tab(tab)


@pytest.fixture
def filetab_and_finder(filetab):
    actions.get_action('Edit/Find and Replace').callback()
    return (filetab, find.finders[filetab])


def test_finder_creation(filetab):
    assert filetab not in find.finders
    actions.get_action('Edit/Find and Replace').callback()
    assert filetab in find.finders


def test_key_bindings_that_are_annoying_if_they_dont_work(filetab):
    assert filetab.focus_get() is filetab.textwidget

    actions.get_action('Edit/Find and Replace').callback()
    finder = find.finders[filetab]
    filetab.update()
    assert filetab.focus_get() is finder.find_entry

    finder.hide()
    assert filetab.focus_get() is filetab.textwidget


def test_finding(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('end', "this is a test\nthis is fun")

    def search_for(substring):
        # i thought highlight_all_matches() would run automatically, it works
        # irl but not in tests, even with update()
        finder.find_entry.insert(0, substring)
        finder.highlight_all_matches()
        result = list(map(str, filetab.textwidget.tag_ranges('find_match')))
        finder.find_entry.delete(0, 'end')
        return result

    assert search_for('is') == [
        '1.2', '1.4',       # thIS is a test
        '1.5', '1.7',       # this IS a test
        '2.2', '2.4',       # thIS is fun
        '2.5', '2.7',       # this IS fun
    ]
    assert search_for('n') == [
        '2.10', '2.11',     # fuN
    ]

    # corner case: match in the beginning of file
    assert search_for('this is a') == ['1.0', '1.9']


def test_set_status(filetab_and_finder):
    finder = filetab_and_finder[1]
    old_fg = str(finder.statuslabel['foreground'])

    finder.set_status("hello")
    assert str(finder.statuslabel['foreground']) == old_fg
    assert finder.statuslabel['text'] == "hello"

    finder.set_status("omg", error=True)
    assert str(finder.statuslabel['foreground']) == 'red'
    assert finder.statuslabel['text'] == "omg"

    finder.set_status("hello")
    assert str(finder.statuslabel['foreground']) == old_fg
    assert finder.statuslabel['text'] == "hello"


def click_button(parent_widget, button_text):
    def recurser(widget):
        count = 0
        if isinstance(widget, ttk.Button) and widget['text'] == button_text:
            widget.tk.call(widget['command'])
            count += 1
        for child in widget.winfo_children():
            count += recurser(child)
        return count

    assert recurser(parent_widget) == 1  # exactly 1 button was found & clicked


# porcusession to avoid creating a root window that messes things up
def test_click_button_util(porcusession):
    frame = ttk.Frame()
    result = []
    ttk.Button(frame, text="Asd", command=(lambda: result.append(1))).pack()
    ttk.Button(ttk.Frame(frame),   # more nesting
               text="Toot", command=(lambda: result.append(2))).pack()
    click_button(frame, "Asd")
    click_button(frame, "Toot")
    ttk.Button(frame, text="Asd", command=(lambda: result.append(1))).pack()
    assert result == [1, 2]

    with pytest.raises(AssertionError):
        click_button(frame, "Asd")


def test_previous_and_next_match_buttons(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', 'asd asd asd\nasd asd')
    filetab.textwidget.mark_set('insert', '1.0')

    finder.find_entry.insert(0, "no matches for this")
    finder.highlight_all_matches()
    click_button(finder, "Next match")
    assert finder.statuslabel['text'] == "No matches found!"
    finder.find_entry.delete(0, 'end')

    finder.find_entry.insert(0, "asd")
    finder.highlight_all_matches()

    def get_selected():
        start, end = filetab.textwidget.tag_ranges('sel')
        assert filetab.textwidget.index('insert') == str(start)
        return (str(start), str(end))

    selecteds = [
        ('1.0', '1.3'),
        ('1.4', '1.7'),
        ('1.8', '1.11'),
        ('2.0', '2.3'),
        ('2.4', '2.7'),
    ]

    tag_locations = filetab.textwidget.tag_ranges('find_match')
    flatten = itertools.chain.from_iterable
    assert list(map(str, tag_locations)) == list(flatten(selecteds))

    index = 0
    for lol in range(500):  # many times back and forth to check corner cases
        if random.choice([True, False]):
            click_button(finder, "Previous match")
            index = (index - 1) % len(selecteds)
        else:
            click_button(finder, "Next match")
            index = (index + 1) % len(selecteds)

        assert finder.statuslabel['text'] == ""
        assert selecteds[index] == get_selected()
