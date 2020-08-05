import itertools
import json
import pathlib
import tempfile
import tkinter.font

import pytest

from porcupine import dirs, settings


@pytest.fixture
def cleared_settings(monkeypatch, porcusession, tmpdir):
    monkeypatch.setattr(settings, '_options', {})
    monkeypatch.setattr(settings, '_json_file_contents', {})
    monkeypatch.setattr(settings, '_FILE_PATH',
                        pathlib.Path(tmpdir) / 'settings.json')
    yield



def load_from_json_string(json_string: str) -> None:
    with settings._FILE_PATH.open('x', encoding='utf-8') as file:
        file.write(json_string)
    settings._load_from_file()


def save_and_read_file() -> str:
    settings.save()
    with settings._FILE_PATH.open('r', encoding='utf-8') as file:
        return json.load(file)


def test_add_option_and_get_and_set(cleared_settings):
    settings.add_option('how_many_foos', 123)
    settings.add_option('bar_message', 'hello')

    assert settings.get('how_many_foos', int) == 123
    assert settings.get('bar_message', str) == 'hello'
    settings.set('how_many_foos', 456)
    settings.set('bar_message', 'bla')
    assert settings.get('how_many_foos', int) == 456
    assert settings.get('bar_message', str) == 'bla'


# Consider this situation:
#   - User installs plugin that adds an option
#   - User uninstalls plugin, which leaves the option to the settings file
#   - User restarts porcupine
#
# Even if the plugin is installed, reading the file happens before add_option()
# is called.
def test_unknown_option_in_settings_file(cleared_settings):
    load_from_json_string('{"foo": "custom", "unknown": "hello"}')
    with pytest.raises(KeyError):
        settings.get('foo', str)

    settings.add_option('foo', 'default')
    assert settings.get('foo', str) == 'custom'
    settings.set('foo', 'default')
    assert settings.get('foo', str) == 'default'

    assert save_and_read_file() == {'unknown': 'hello'}


#def test_variables_cached_properly(cleared_settings):
#    settings.add_option('thingy_count', 123)
#
#    # If variables were not cached, then this would create a temporary Variable
#    # object and garbage collect it immediately (because refcount goes to zero)
#    # and that would destroy the underlying Tcl variable...
#    settings.get_var('thingy_count', tkinter.IntVar)
#
#    # ...which would cause this to fail:
#    assert settings.get_var('thingy_count', tkinter.IntVar).get() == 123


def test_wrong_type(cleared_settings):
    settings.add_option('magic_message', 'bla')

#    with pytest.raises(TypeError, match=r'^use StringVar instead of IntVar$'):
#        settings.get_var('magic_message', tkinter.IntVar)
    with pytest.raises(TypeError, match=r'^use str instead of int$'):
        settings.get('magic_message', int)
    with pytest.raises(TypeError, match=r'^expected str, got int$'):
        settings.set('magic_message', 123)


def test_name_collision(cleared_settings):
    settings.add_option('omg', 'bla')
    with pytest.raises(RuntimeError, match="^there's already an option named 'omg'$"):
        settings.add_option('omg', 'bla')


def test_reset(cleared_settings):
    load_from_json_string('{"foo": "custom", "bar": "custom", "unknown": "hello"}')
    settings.add_option('foo', 'default')
    settings.add_option('bar', 'default')
    settings.add_option('baz', 'default')
    assert settings.get('foo', str) == 'custom'
    assert settings.get('bar', str) == 'custom'
    assert settings.get('baz', str) == 'default'

    settings.reset('bar')
    assert settings.get('foo', str) == 'custom'
    assert settings.get('bar', str) == 'default'
    assert settings.get('baz', str) == 'default'
    assert save_and_read_file() == {'foo': 'custom', 'unknown': 'hello'}

    settings.reset_all()
    assert settings.get('foo', str) == 'default'
    assert settings.get('bar', str) == 'default'
    assert settings.get('baz', str) == 'default'
    assert save_and_read_file() == {}  # even unknown options go away


def test_no_json_file(cleared_settings):
    assert not settings._FILE_PATH.exists()
    settings._load_from_file()

    settings.add_option('foo', 'default')
    settings.set('foo', 'custom')

    assert not settings._FILE_PATH.exists()
    settings.reset_all()
    assert settings.get('foo', str) == 'default'


def test_save(cleared_settings):
    load_from_json_string('{"bar": "custom bar"}')

    settings.add_option('foo', 'default')
    settings.add_option('bar', 'default')
    settings.add_option('baz', 'default')
    settings.set('foo', 'custom foo')

    settings.save()
    with settings._FILE_PATH.open('r') as file:
        assert json.load(file) == {'foo': 'custom foo', 'bar': 'custom bar'}


def test_font_gets_updated(porcusession):
    fixedfont = tkinter.font.Font(name='TkFixedFont', exists=True)

    settings.set('font_family', 'Helvetica')
    assert fixedfont.cget('family') == 'Helvetica'
    settings.set('font_size', 123)
    assert fixedfont.cget('size') == 123


def test_init_when_already_inited(porcusession):
    with pytest.raises(RuntimeError, match=r"^can't call _init\(\) twice$"):
        settings._init()
