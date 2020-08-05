import dataclasses
import typing

from porcupine import get_main_window, utils


def test_bind_with_data_string(porcusession, mocker):
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


def test_bind_with_data_class(porcusession):
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
