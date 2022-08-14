import dataclasses
import json
import sys
import tkinter
from pathlib import Path
from tkinter import ttk
from tkinter.font import Font
from typing import Optional

import dacite
import pytest

from porcupine import settings, utils
from porcupine.settings import global_settings


@pytest.fixture(autouse=True)
def restore_default_settings():
    yield

    # We don't clear the user's settings, porcupine.dirs is monkeypatched
    if sys.platform == "win32":
        assert "Temp" in settings.get_json_path().parts
    else:
        assert Path.home() not in settings.get_json_path().parents
    global_settings.reset_all()


# Could replace some of this with non-global setting objects, but I don't feel
# like rewriting the tests just because it would be slightly nicer that way
@pytest.fixture
def cleared_global_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(global_settings, "_options", {})
    monkeypatch.setattr(global_settings, "_unknown_options", {})
    monkeypatch.setattr(settings, "get_json_path", (lambda: tmp_path / "settings.json"))


def load_from_json_string(json_string: str) -> None:
    with settings.get_json_path().open("x", encoding="utf-8") as file:
        file.write(json_string)
    settings._load_from_file()


def save_and_read_file() -> str:
    settings.save()
    with settings.get_json_path().open("r", encoding="utf-8") as file:
        return json.load(file)


def test_add_option_and_get_and_set(cleared_global_settings):
    global_settings.add_option("how_many_foos", 123)
    global_settings.add_option("bar_message", "hello")

    assert global_settings.get("how_many_foos", int) == 123
    assert global_settings.get("bar_message", str) == "hello"
    global_settings.set("how_many_foos", 456)
    global_settings.set("bar_message", "bla")
    assert global_settings.get("how_many_foos", int) == 456
    assert global_settings.get("bar_message", str) == "bla"


# Consider this situation:
#   - User installs plugin that adds an option
#   - User uninstalls plugin, which leaves the option to the settings file
#   - User restarts porcupine
#
# Even if the plugin is installed, reading the file happens before add_option()
# is called.
def test_unknown_option_in_settings_file(cleared_global_settings):
    load_from_json_string('{"foo": "custom", "unknown": "hello"}')
    with pytest.raises(KeyError):
        global_settings.get("foo", str)

    global_settings.add_option("foo", "default")
    assert global_settings.get("foo", str) == "custom"
    global_settings.set("foo", "default")
    assert global_settings.get("foo", str) == "default"

    assert save_and_read_file() == {"unknown": "hello"}


def test_wrong_type(cleared_global_settings):
    global_settings.add_option("magic_message", "bla")

    with pytest.raises(
        dacite.exceptions.WrongTypeError,
        match=r'wrong value type .* should be "int" instead of .* "str"',
    ):
        global_settings.get("magic_message", int)
    with pytest.raises(
        dacite.exceptions.WrongTypeError,
        match=r'wrong value type .* should be "str" instead of .* "int"',
    ):
        global_settings.set("magic_message", 123)


def test_name_collision(cleared_global_settings):
    global_settings.add_option("omg", "bla")
    with pytest.raises(RuntimeError, match="^there's already an option named 'omg'$"):
        global_settings.add_option("omg", "bla")

    global_settings.add_option("omg", "bla", exist_ok=True)
    with pytest.raises(AssertionError):
        global_settings.add_option("omg", 123, exist_ok=True)


def test_reset(cleared_global_settings):
    load_from_json_string('{"foo": "custom", "bar": "custom", "unknown": "hello"}')
    global_settings.add_option("foo", "default")
    global_settings.add_option("bar", "default")
    global_settings.add_option("baz", "default")
    assert global_settings.get("foo", str) == "custom"
    assert global_settings.get("bar", str) == "custom"
    assert global_settings.get("baz", str) == "default"

    global_settings.reset("bar")
    assert global_settings.get("foo", str) == "custom"
    assert global_settings.get("bar", str) == "default"
    assert global_settings.get("baz", str) == "default"
    assert save_and_read_file() == {"foo": "custom", "unknown": "hello"}

    global_settings.reset_all()
    assert global_settings.get("foo", str) == "default"
    assert global_settings.get("bar", str) == "default"
    assert global_settings.get("baz", str) == "default"
    assert save_and_read_file() == {}  # even unknown options go away


def test_no_json_file(cleared_global_settings):
    assert not settings.get_json_path().exists()
    settings._load_from_file()

    global_settings.add_option("foo", "default")
    global_settings.set("foo", "custom")

    assert not settings.get_json_path().exists()
    global_settings.reset_all()
    assert global_settings.get("foo", str) == "default"


def test_save(cleared_global_settings):
    load_from_json_string('{"bar": "custom bar"}')

    global_settings.add_option("foo", "default")
    global_settings.add_option("bar", "default")
    global_settings.add_option("baz", "default")
    global_settings.set("foo", "custom foo")

    settings.save()
    with settings.get_json_path().open("r") as file:
        assert json.load(file) == {"foo": "custom foo", "bar": "custom bar"}


def test_font_gets_updated():
    fixedfont = Font(name="TkFixedFont", exists=True)

    global_settings.set("font_family", "Helvetica")
    assert fixedfont["family"] == "Helvetica"
    global_settings.set("font_size", 123)
    assert fixedfont["size"] == 123


@dataclasses.dataclass
class Foo:
    how_many: int
    message: str


def test_dataclass():
    settings_obj = settings.Settings(None, "<<Foo:{}>>")

    settings_obj.add_option("foo", None, Optional[Foo])
    settings_obj.set("foo", {"how_many": 123, "message": "hello"}, from_config=True)
    settings_obj.set("bar", {"how_many": 456, "message": "hi"}, from_config=True)
    settings_obj.add_option("bar", None, Optional[Foo])

    assert settings_obj.get("foo", Foo) == Foo(123, "hello")
    assert settings_obj.get("bar", Foo) == Foo(456, "hi")


def test_debug_dump(capsys):
    settings_obj = settings.Settings(None, "<<Foo:{}>>")
    settings_obj.add_option("foo", None, Optional[str])
    settings_obj.set("bar", ["a", "b", "c"], from_config=True, tag="this is a tag")
    settings_obj.debug_dump()

    output, errors = capsys.readouterr()
    assert not errors
    if sys.version_info < (3, 9):
        output = output.replace("typing.Union[str, NoneType]", "typing.Optional[str]")
    assert (
        output
        == """\
1 known options (add_option called)
  foo = None    (type=typing.Optional[str], tag=None)

1 unknown options (add_option not called)
  bar = ['a', 'b', 'c']    (tag='this is a tag')

"""
    )


def test_font_family_chooser():
    families = settings._get_monospace_font_families()
    assert len(families) == len(set(families)), "duplicates"
    assert families == sorted(families), "wrong order"


@pytest.fixture
def toplevel():
    toplevel = tkinter.Toplevel()
    toplevel.geometry("600x100")
    toplevel.update()
    yield toplevel
    toplevel.destroy()


def test_change_events(toplevel):
    settings_obj = settings.Settings(toplevel, "<<ItChanged:{}>>")
    settings_obj.add_option("foo", default="foo default")
    settings_obj.add_option("bar", default="bar default")

    change_events = []
    toplevel.bind(
        "<<ItChanged:foo>>",
        (lambda e: change_events.append("foo = " + settings_obj.get("foo", str))),
        add=True,
    )
    toplevel.bind(
        "<<ItChanged:bar>>",
        (lambda e: change_events.append("bar = " + settings_obj.get("bar", str))),
        add=True,
    )

    settings_obj.set("foo", "x")
    assert change_events == ["foo = x"]
    settings_obj.set("bar", "y")
    assert change_events == ["foo = x", "bar = y"]

    change_events.clear()
    with settings_obj.set_many_at_once():
        settings_obj.set("foo", "some temporary value")
        settings_obj.set("foo", "xxx")
        settings_obj.set("bar", "yyy")
        assert change_events == []
    assert change_events == ["foo = xxx", "bar = yyy"]

    with settings_obj.set_many_at_once():
        with pytest.raises(RuntimeError, match="cannot be nested"):
            with settings_obj.set_many_at_once():
                pass


def create_paned_window(toplevel):
    pw = utils.PanedWindow(toplevel, orient="horizontal")
    pw.pack(fill="both", expand=True)
    left = ttk.Label(pw, text="aaaaaaaaaaa")
    right = ttk.Label(pw, text="aaaaaaaaaaa")
    pw.add(left)
    pw.add(right)
    settings.remember_pane_size(pw, left, "a_width", 123)
    return (pw, left)


def test_remember_panedwindow_positions(toplevel):
    pw, left = create_paned_window(toplevel)
    pw.update()
    assert left.winfo_width() == 123

    pw.sash_place(0, 44, 0)
    pw.event_generate("<ButtonRelease-1>")  # happens after user drags pane

    pw2, left2 = create_paned_window(toplevel)
    pw.update()

    # it is off-by-one on my computer, that's fine
    assert abs(left2.winfo_width() - 44) < 5
