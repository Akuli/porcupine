# TODO: test overlapping matches

import itertools
import platform
import random
from tkinter import ttk

import pytest

from porcupine import actions, get_main_window, get_tab_manager, tabs
from porcupine.plugins import find


@pytest.fixture
def filetab_and_finder(filetab):
    actions.get_action('Edit/Find and Replace').callback()
    return (filetab, find.finders[filetab])


def test_finder_creation(filetab):
    assert filetab not in find.finders
    actions.get_action('Edit/Find and Replace').callback()
    assert filetab in find.finders


# i don't know why, but this does not work on windows
@pytest.mark.skipif(
    platform.system() == 'Windows',
    reason="focus_get() doesn't work on windows like this test assumes")
def test_key_bindings_that_are_annoying_if_they_dont_work(filetab):
    assert filetab.focus_get() is filetab.textwidget

    actions.get_action('Edit/Find and Replace').callback()
    finder = find.finders[filetab]
    filetab.update()
    assert filetab.focus_get() is finder.find_entry

    finder.hide()
    assert filetab.focus_get() is filetab.textwidget


def click(button):
    button.tk.call(button['command'])


# porcusession to avoid creating another root window that messes things up
def test_click_util(porcusession):
    result = []
    asd = ttk.Button(get_main_window(),
                     command=(lambda: result.append(1)))
    click(asd)
    assert result == [1]


def test_initial_button_states(filetab_and_finder):
    finder = filetab_and_finder[1]
    all_buttons = [finder.previous_button, finder.next_button,
                   finder.replace_this_button, finder.replace_all_button]

    # all buttons should be disabled because the find entry is empty
    assert finder.statuslabel['text'] == "Type something to find."
    for button in all_buttons:
        assert str(button['state']) == 'disabled'

    # i had a bug that occurred when typing something to the find area and
    # backspacing it out because it called highlight_all_matches()
    finder.highlight_all_matches()
    assert finder.statuslabel['text'] == "Type something to find."
    for button in all_buttons:
        assert str(button['state']) == 'disabled'


def test_initial_checkbox_states(filetab_and_finder):
    finder = filetab_and_finder[1]
    assert not finder.ignore_case_var.get()


def test_finding(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('end', "this is a test\nthis is fun")

    def search_for(substring):
        # i thought highlight_all_matches() would run automatically, it works
        # irl but not in tests, even with update()
        finder.find_entry.insert(0, substring)
        finder.highlight_all_matches()
        result = list(
            map(str, filetab.textwidget.tag_ranges('find_highlight')))
        finder.find_entry.delete(0, 'end')

        buttons = [finder.previous_button, finder.next_button,
                   finder.replace_all_button]
        states = {str(button['state']) for button in buttons}
        assert len(states) == 1, "not all buttons have the same state"

        if finder.statuslabel['text'] == "Found no matches :(":
            assert states == {'disabled'}
        else:
            assert states == {'normal'}

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

    assert search_for('This Is A') == []
    assert finder.statuslabel['text'] == "Found no matches :("


def test_ignore_case_and_full_words_only(filetab_and_finder):
    filetab, finder = filetab_and_finder

    def find_stuff():
        finder.highlight_all_matches()
        return list(
            map(str, filetab.textwidget.tag_ranges('find_highlight')))

    filetab.textwidget.insert('1.0', "Asd asd dasd asd asda asd ASDA ASD")
    finder.find_entry.insert(0, "asd")

    assert find_stuff() == [
        '1.4', '1.7',
        '1.9', '1.12',
        '1.13', '1.16',
        '1.17', '1.20',
        '1.22', '1.25',
    ]

    finder.full_words_var.set(True)
    assert find_stuff() == [
        '1.4', '1.7',
        '1.13', '1.16',
        '1.22', '1.25',
    ]

    finder.ignore_case_var.set(True)
    assert find_stuff() == [
        '1.0', '1.3',
        '1.4', '1.7',
        '1.13', '1.16',
        '1.22', '1.25',
        '1.31', '1.34',
    ]

    finder.full_words_var.set(False)
    assert find_stuff() == [
        '1.0', '1.3',
        '1.4', '1.7',
        '1.9', '1.12',
        '1.13', '1.16',
        '1.17', '1.20',
        '1.22', '1.25',
        '1.26', '1.29',
        '1.31', '1.34',
    ]


def test_basic_statuses_and_previous_and_next_match_buttons(
        filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', 'asd asd asd\nasd asd')
    filetab.textwidget.mark_set('insert', '1.0')

    finder.find_entry.insert(0, "no matches for this")
    finder.highlight_all_matches()
    assert finder.statuslabel['text'] == "Found no matches :("

    for button in [finder.previous_button, finder.next_button,
                   finder.replace_all_button]:
        assert str(button['state']) == 'disabled'

    for button in [finder.previous_button, finder.next_button]:
        # the button is disabled, but key bindings can call its command, and
        # click(button) works of course
        finder.statuslabel['text'] = "this should be overwritten"
        click(button)
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
            click(finder.previous_button)
            index = (index - 1) % len(selecteds)
        else:
            click(finder.next_button)
            index = (index + 1) % len(selecteds)

        assert finder.statuslabel['text'] == ""
        assert selecteds[index] == get_selected()


def test_replace(filetab_and_finder):
    # replacing 'asd' with 'asda' tests corner cases well because:
    #   - 'asda' contains 'asd', so must avoid infinite loops
    #   - replacing 'asd' with 'asda' throws off indexes after the replaced
    #     area, and the finder must handle this
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asda")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    # the button is disabled, but key bindings can still call its callback, and
    # the callback should set a nice message to statuslabel
    click(finder.replace_this_button)
    assert finder.statuslabel['text'] == (
        'Click "Previous match" or "Next match" first.')

    click(finder.next_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match. There are 2 more matches.")
    assert finder.get_match_ranges() == [('1.5', '1.8'), ('1.9', '1.12')]

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match. There is 1 more match.")
    assert finder.get_match_ranges() == [('1.10', '1.13')]

    assert str(finder.previous_button['state']) == 'normal'
    assert str(finder.next_button['state']) == 'normal'

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert str(finder.previous_button['state']) == 'disabled'
    assert str(finder.next_button['state']) == 'disabled'
    assert str(finder.replace_all_button['state']) == 'disabled'
    assert finder.statuslabel['text'] == "Replaced the last match."
    assert finder.get_match_ranges() == []


# if this passes with no code to specially handle this, the replacing code
# seems to handle corner cases well
def test_replace_asd_with_asd(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asd")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7')]

    click(finder.next_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7')]

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match. There is 1 more match.")
    assert finder.get_match_ranges() == [('1.4', '1.7')]

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert finder.statuslabel['text'] == "Replaced the last match."
    assert finder.get_match_ranges() == []


def test_replace_all(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('1.0', "asd asd asd")
    finder.find_entry.insert(0, "asd")
    finder.replace_entry.insert(0, "asda")

    finder.highlight_all_matches()
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    click(finder.next_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.get_match_ranges() == [('1.0', '1.3'), ('1.4', '1.7'),
                                         ('1.8', '1.11')]

    click(finder.replace_this_button)
    assert str(finder.replace_this_button['state']) == 'normal'
    assert finder.statuslabel['text'] == (
        "Replaced a match. There are 2 more matches.")
    assert finder.get_match_ranges() == [('1.5', '1.8'), ('1.9', '1.12')]

    click(finder.replace_all_button)
    assert str(finder.replace_this_button['state']) == 'disabled'
    assert str(finder.previous_button['state']) == 'disabled'
    assert str(finder.next_button['state']) == 'disabled'
    assert str(finder.replace_all_button['state']) == 'disabled'
    assert finder.statuslabel['text'] == "Replaced 2 matches."
    assert finder.get_match_ranges() == []
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'asda asda asda'

    filetab.textwidget.delete('1.3', 'end')
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'asd'
    finder.highlight_all_matches()
    assert str(finder.replace_all_button['state']) == 'normal'
    click(finder.replace_all_button)
    assert filetab.textwidget.get('1.0', 'end - 1 char') == 'asda'
    assert finder.statuslabel['text'] == "Replaced 1 match."


def test_selecting_messing_up_button_disableds(filetab_and_finder):
    filetab, finder = filetab_and_finder
    filetab.textwidget.insert('end', "asd")

    finder.find_entry.insert(0, "asd")
    finder.highlight_all_matches()

    click(finder.next_button)
    assert str(finder.replace_this_button['state']) == 'normal'

    # "Replace this match" doesn't make sense after changing the selection
    # because no match is selected to be the "this" match
    filetab.textwidget.tag_remove('sel', '1.2', 'end')
    filetab.update()
    assert filetab.textwidget.get('sel.first', 'sel.last') == 'as'
    assert str(finder.replace_this_button['state']) == 'disabled'
