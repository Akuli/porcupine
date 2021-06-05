import pathlib
import shutil
import subprocess

import pytest

from porcupine.plugins.mergeconflict import ConflictDisplayer, find_merge_conflicts

# Indented to not trigger the plugin when editing this file
merge_conflict_string = '''\
    before
    <<<<<<< HEAD
    hello there
    =======
    hello world
    >>>>>>> other_branch
    after
    '''.replace(
    ' ' * 4, ''
)


@pytest.mark.skipif(shutil.which('git') is None, reason="need git to make merge conflicts")
def test_merge_conflict_string(tmp_path, monkeypatch, capfd):
    monkeypatch.chdir(tmp_path)
    file_content = 'before\nhello\nafter\n'

    subprocess.run(['git', 'init'])
    # No --global, only affects test repo
    subprocess.run(['git', 'config', 'user.name', 'foo'])
    subprocess.run(['git', 'config', 'user.email', 'foo@example.com'])

    pathlib.Path('foo.txt').write_text(file_content)
    subprocess.run(['git', 'add', 'foo.txt'])
    subprocess.run(['git', 'commit', '-m', 'create foo.txt'])
    subprocess.run(['git', 'checkout', '-b', 'other_branch'])
    pathlib.Path('foo.txt').write_text(file_content.replace('hello', 'hello world'))
    subprocess.run(['git', 'commit', '--all', '-m', 'hello there'])
    subprocess.run(['git', 'checkout', 'master'])
    pathlib.Path('foo.txt').write_text(file_content.replace('hello', 'hello there'))
    subprocess.run(['git', 'commit', '--all', '-m', 'hello my friend'])
    subprocess.run(['git', 'merge', 'other_branch'])
    assert pathlib.Path('foo.txt').read_text() == merge_conflict_string
    capfd.readouterr()  # hide unnecessary prints from git


def test_find_merge_conflicts(filetab):
    text = filetab.textwidget
    text.insert('end - 1 char', merge_conflict_string)
    assert find_merge_conflicts(text) == [[2, 4, 6]]
    text.insert('end - 1 char', merge_conflict_string)
    assert find_merge_conflicts(text) == [[2, 4, 6], [9, 11, 13]]

    text.insert('2.1', '<')  # too many '<' characters
    assert find_merge_conflicts(text) == []  # it gave up
    text.delete('2.1')
    assert find_merge_conflicts(text) == [[2, 4, 6], [9, 11, 13]]

    # ruin last end marker, make it give up
    text.delete(text.search('>', 'end', backwards=True))
    assert find_merge_conflicts(text) == []


def test_not_modified(filetab, tmp_path):
    filetab.path = tmp_path / 'foo.txt'
    filetab.path.write_text(merge_conflict_string)
    filetab.reload()
    assert not filetab.is_modified()


def check_use_button(textwidget, button_number):
    textwidget.delete('1.0', 'end')
    textwidget.insert('1.0', merge_conflict_string)
    displayer = ConflictDisplayer(textwidget, *find_merge_conflicts(textwidget)[0])
    textwidget.insert('2.0', 'lol\nwat\n')
    {1: displayer.part1_button, 2: displayer.part2_button}[button_number].invoke()
    textwidget.update()
    return textwidget.get('1.0', 'end - 1 char')


def test_use_buttons(filetab):
    assert check_use_button(filetab.textwidget, 1) == 'before\nlol\nwat\nhello there\nafter\n'
    assert check_use_button(filetab.textwidget, 2) == 'before\nlol\nwat\nhello world\nafter\n'
