import json

from porcupine import get_main_window, utils


def test_bind_with_data(porcusession):
    ran = 0

    # i don't know why the main window works better with this than a
    # temporary tkinter.Frame()
    def cb(event):
        assert event.widget is get_main_window()
        assert event.data_string == '{"a": ["b", "c"]}'
        assert event.data_json() == {'a': ['b', 'c']}
        nonlocal ran
        ran += 1

    utils.bind_with_data(get_main_window(), '<<Asd>>', cb, add=True)
    get_main_window().event_generate(
        '<<Asd>>', data=json.dumps({'a': ['b', 'c']}))
    assert ran == 1
