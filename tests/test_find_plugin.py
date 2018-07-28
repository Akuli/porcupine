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
        result = list(map(str, filetab.textwidget.tag_ranges('find_highlight')))
        finder.find_entry.delete(0, 'end')
        return result

    assert search_for('is') == [
        '1.2', '1.4',       # thIS is a test
        '1.5', '1.7',       # this IS a test
        '2.2', '2.4',       # thIS is fun
        '2.5', '2.7',       # this IS fun
    ]
    assert finder.statuslabel['text'] == "Found 4 matches."

    assert search_for('n') == [
        '2.10', '2.11',     # fuN
    ]
    assert finder.statuslabel['text'] == "Found 1 match."

    # corner case: match in the beginning of file
    assert search_for('this is a') == ['1.0', '1.9']
    assert finder.statuslabel['text'] == "Found 1 match."

    assert search_for('this is not anywhere in the test text') == []
    assert finder.statuslabel['text'] == "Found no matches :("


def find_button(parent_widget, button_text):
    def recurser(widget):
        if isinstance(widget, ttk.Button) and widget['text'] == button_text:
            yield widget
        for child in widget.winfo_children():
            yield from recurser(child)

    [button] = recurser(parent_widget)  # fails if there's not exactly 1 button
    return button


def click(button):
    button.tk.call(button['command'])


# porcusession to avoid creating a root window that messes things up
def test_button_utils(porcusession):
    frame = ttk.Frame()
    result = []
    ttk.Button(frame, text="Asd", command=(lambda: result.append(1))).pack()
    ttk.Button(ttk.Frame(frame),   # more nesting
               text="Toot", command=(lambda: result.append(2))).pack()
    click(find_button(frame, "Asd"))
    click(find_button(frame, "Toot"))
    ttk.Button(frame, text="Asd", command=(lambda: result.append(1))).pack()
    assert result == [1, 2]

    with pytest.raises(ValueError):
        find_button(frame, "Asd")


def test_basic_statuses_and_previous_and_next_match_buttons(
        filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', 'asd asd asd\nasd asd')
    filetab.textwidget.mark_set('insert', '1.0')

    finder.find_entry.insert(0, "no matches for this")
    finder.highlight_all_matches()
    assert finder.statuslabel['text'] == "Found no matches :("
    click(find_button(finder, "Next match"))
    assert finder.statuslabel['text'] == "No matches found!"
    finder.find_entry.delete(0, 'end')

    finder.find_entry.insert(0, "asd")
    finder.highlight_all_matches()
    assert finder.statuslabel['text'] == "Found 5 matches."

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

    tag_locations = filetab.textwidget.tag_ranges('find_highlight')
    flatten = itertools.chain.from_iterable
    assert list(map(str, tag_locations)) == list(flatten(selecteds))

    index = 0
    for lol in range(500):   # many times back and forth to check corner cases
        if random.choice([True, False]):
            click(find_button(finder, "Previous match"))
            index = (index - 1) % len(selecteds)
        else:
            click(find_button(finder, "Next match"))
            index = (index + 1) % len(selecteds)

        assert finder.statuslabel['text'] == ""
        assert selecteds[index] == get_selected()


def test_replace(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd")
    finder.replace_entry.insert(0, "toot")
    replace_this_button = find_button(finder, "Replace this match")
    assert str(replace_this_button['state']) == 'disabled'

    finder.find_entry.insert(0, "asd")
    finder.highlight_all_matches()
    assert str(replace_this_button['state']) == 'disabled'

    # TODO: click the button anyway, even though it's disabled, the key
    #       bindings do it and it should create a nice status message

    click(find_button(finder, "Next match"))
    assert str(replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7')]

    click(replace_this_button)
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'toot asd'
    assert str(replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.5', '1.8')]

    click(replace_this_button)
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'toot toot'
    assert str(replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == []


def test_replace(filetab_and_finder):
    # replacing 'asd' with 'asda' tests corner cases well because:
    #   - 'asda' contains 'asd', so must avoid infinite loops
    #   - replacing 'asd' with 'asda' throws off indexes after the replaced
    #     area, and the finder must handle this
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asda")
    replace_this_button = find_button(finder, "Replace this match")

    finder.highlight_all_matches()
    assert str(replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    click(find_button(finder, "Next match"))
    assert str(replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    click(replace_this_button)
    assert str(replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match.\nThere are 2 more matches.")
    assert finder.get_match_ranges() == [('1.5', '1.8'), ('1.9', '1.12')]

    click(replace_this_button)
    assert str(replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match.\nThere is 1 more match.")
    assert finder.get_match_ranges() == [('1.10', '1.13')]

    click(replace_this_button)
    assert str(replace_this_button['state']) == 'disabled'
    assert finder.statuslabel['text'] == "Replaced the last match."
    assert finder.get_match_ranges() == []


# if this passes with no code to specially handle this, the replacing code
# seems to handle corner cases well
def test_replace_asd_with_asd(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asd")
    replace_this_button = find_button(finder, "Replace this match")

    finder.highlight_all_matches()
    assert str(replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7')]

    click(find_button(finder, "Next match"))
    assert str(replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7')]

    click(replace_this_button)
    assert str(replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match.\nThere is 1 more match.")
    assert finder.get_match_ranges() == [('1.4', '1.7')]

    click(replace_this_button)
    assert str(replace_this_button['state']) == 'disabled'
    assert finder.statuslabel['text'] == "Replaced the last match."
    assert finder.get_match_ranges() == []
