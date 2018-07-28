import contextlib

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
        # irl but not in this test, even with update()
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
