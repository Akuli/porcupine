import tkinter

import pytest

from porcupine import get_main_window, utils
from porcupine.textwidget import Change, Changes, change_batch, create_peer_widget, track_changes


@pytest.fixture(scope='function')
def text_and_events():
    text = tkinter.Text(get_main_window())
    text.config(undo=True)    # must be before track_changes()
    track_changes(text)

    # peers can mess things up
    create_peer_widget(text, tkinter.Text(get_main_window()))

    events = []
    utils.bind_with_data(text, '<<ContentChanged>>', events.append, add=True)
    yield (text, events)
    assert not events


def test_insert_basic(text_and_events):
    text, events = text_and_events
    text.insert('end', 'foo')
    text.update()

    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.0', end='1.0', old_text_len=0, new_text='foo'),
    ]


def test_delete_basic(text_and_events):
    text, events = text_and_events

    text.insert('end', 'foobarbaz')
    text.update()
    events.pop()

    text.delete('1.6', '1.8')
    text.update()
    assert text.get('1.0', 'end - 1 char') == 'foobarz'
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.6', end='1.8', old_text_len=2, new_text=''),
    ]

    text.delete('1.4')
    text.update()
    assert text.get('1.0', 'end - 1 char') == 'foobrz'
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.4', end='1.5', old_text_len=1, new_text=''),
    ]


def test_delete_many_args(text_and_events):
    text, events = text_and_events

    text.insert('end', 'foobar')
    text.update()
    events.pop()

    # tkinter doesn't support weirder ways to delete
    text.tk.call(text, 'delete', '1.3', '1.5', '1.4', '1.6', '1.0')
    text.update()
    assert text.get('1.0', 'end - 1 char') == 'oo'
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.3', end='1.6', old_text_len=3, new_text=''),
        Change(start='1.0', end='1.1', old_text_len=1, new_text=''),
    ]

    for args in [('1.4', '1.6', '1.4', '1.5'),
                 ('1.4', '1.5', '1.4', '1.6')]:
        text.delete('1.0', 'end')
        text.insert('1.0', 'hello world')
        text.update()
        events.clear()

        text.tk.call(text, 'delete', *args)
        text.update()
        assert text.get('1.0', 'end - 1 char') == 'hellworld'
        assert events.pop().data_class(Changes).change_list == [
            Change(start='1.4', end='1.6', old_text_len=2, new_text=''),
        ]


def test_replace_at_very_end(text_and_events):
    text, events = text_and_events

    text.insert('end', 'foo')
    text.update()
    events.pop()

    text.replace('end', 'end', 'bar')
    text.update()
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.3', end='1.3', old_text_len=0, new_text='bar'),
    ]


def test_undo(text_and_events):
    text, events = text_and_events

    text.insert('end', 'a')
    text.update()
    assert text.get('1.0', 'end - 1 char') == 'a'
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.0', end='1.0', old_text_len=0, new_text='a'),
    ]

    text.edit_undo()
    text.update()
    assert text.get('1.0', 'end - 1 char') == ''
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.0', end='1.1', old_text_len=1, new_text=''),
    ]


def test_track_changes_twice():
    text = tkinter.Text(get_main_window())
    track_changes(text)
    with pytest.raises(RuntimeError, match=r'^track_changes\(\) called twice for same text widget$'):
        track_changes(text)


def test_track_changes_after_create_peer_widget():
    text = tkinter.Text(get_main_window())
    peer = tkinter.Text(get_main_window())
    create_peer_widget(text, peer)

    with pytest.raises(RuntimeError, match=r'^track_changes\(\) must be called before create_peer_widget\(\)$'):
        track_changes(text)
    with pytest.raises(RuntimeError, match=r'^track_changes\(\) must be called before create_peer_widget\(\)$'):
        track_changes(peer)


def test_change_batch_no_tracking():
    text = tkinter.Text(get_main_window())
    with change_batch(text):    # should do nothing
        text.insert('end', 'hello\n')


def test_change_batch_with_tracking(text_and_events):
    text, events = text_and_events
    with change_batch(text):
        end = 'end - 1 char'
        text.insert(end, 'hello ')
        text.insert(end, 'there')
        text.delete(f'{end} - 5 chars', end)
        text.insert(end, 'world')
    assert text.get('1.0', end) == 'hello world'

    text.update()
    assert len(events) == 1    # would be multiple events without change_batch
    assert events.pop().data_class(Changes).change_list == [
        Change(start='1.0', end='1.0', old_text_len=0, new_text='hello '),
        Change(start='1.6', end='1.6', old_text_len=0, new_text='there'),
        Change(start='1.6', end='1.11', old_text_len=5, new_text=''),
        Change(start='1.6', end='1.6', old_text_len=0, new_text='world'),
    ]


def test_change_batch_nested(text_and_events):
    text, events = text_and_events
    with pytest.raises(RuntimeError, match='nested calls'):
        with change_batch(text):
            with change_batch(text):
                pass


def test_peer_cursor_moved(text_and_events):
    text, change_events = text_and_events
    peer = tkinter.Text(get_main_window())
    create_peer_widget(text, peer)

    text.insert('1.0', 'hello world')
    text.mark_set('insert', '1.5')
    peer.mark_set('insert', '1.5')
    change_events.clear()

    text_move_events = []
    peer_move_events = []
    text.bind('<<CursorMoved>>', text_move_events.append)
    peer.bind('<<CursorMoved>>', peer_move_events.append)

    text.mark_set('insert', 'end')
    assert not peer_move_events
    assert len(text_move_events) == 1
    text_move_events.clear()

    peer.mark_set('insert', 'end')
    assert not text_move_events
    assert len(peer_move_events) == 1
    peer_move_events.clear()
