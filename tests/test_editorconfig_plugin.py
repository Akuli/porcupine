import logging
import pathlib

from porcupine import settings
from porcupine.plugins.editorconfig import apply_config, get_config, glob_match


def test_glob():
    assert glob_match(r"star\*file\*name", "star*file*name")
    assert not glob_match(r"star\*file\*name", "starFOOfileFOOname")

    assert glob_match("*.py", "foo.py")
    assert not glob_match("*.py", "foo.js")
    assert glob_match("*.py", ".py")
    assert not glob_match("*.py", "foo/bar.py")

    assert glob_match("**.py", "foo.py")
    assert not glob_match("**.py", "foo.js")
    assert glob_match("**.py", ".py")
    assert glob_match("**.py", "foo/bar.py")

    assert glob_match("*.{py,js}", "foo.py")
    assert glob_match("*.{py,js}", "foo.js")
    assert not glob_match("*.{py,js}", "foo.json")

    assert glob_match("?ython", "python")
    assert glob_match("?ython", "cython")
    assert glob_match("?ython", "jython")
    assert not glob_match("?ython", "mypy")

    assert glob_match("foo[a-c].py", "fooa.py")
    assert glob_match("foo[a-c].py", "foo-.py")
    assert glob_match("foo[a-c].py", "fooc.py")
    assert not glob_match("foo[a-c].py", "foob.py")
    assert not glob_match("foo[a-c].py", "food.py")

    assert glob_match("foo[!a].py", "food.py")
    assert not glob_match("foo[!a].py", "fooa.py")
    assert not glob_match("foo[!a].py", "foobar.py")
    assert not glob_match("foo[!a].py", "foo.py")

    assert glob_match("foo.{py,js}", "foo.py")
    assert glob_match("foo.{py,js}", "foo.js")
    assert not glob_match("foo.{py,js}", "foo.c")
    assert not glob_match("foo.{py,js}", "bar.js")

    for n in range(-50, 50):
        if -2 <= n <= 14:
            assert glob_match("foo{-2..14}.py", f"foo{n}.py")
        else:
            assert not glob_match("foo{-2..14}.py", f"foo{n}.py")


TEST_DATA_DIR = pathlib.Path(__file__).absolute().parent / "editorconfig_test_data"


def test_funny_files():
    code_file = TEST_DATA_DIR / "foo" / "a.py"
    assert get_config(code_file) == {
        # no indent_style, foo/.editorconfig unsets it
        "indent_size": "4",  # foo/.editorconfig takes precedence
        "end_of_line": "crlf",  # only in non-foo .editorconfig
        "trim_trailing_whitespace": "true",  # only in foo/.editorconfig
    }


def test_example_file_from_editorconfig_org():
    path = TEST_DATA_DIR / "editorconfig_org"
    assert (path / ".editorconfig").is_file()

    assert get_config(path / "matches the star") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
    }
    assert get_config(path / "foo.py") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "charset": "utf-8",
        "indent_style": "space",
        "indent_size": "4",
    }
    assert get_config(path / "foo.js") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "charset": "utf-8",
    }
    assert get_config(path / "lib" / "foo.js") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "charset": "utf-8",
        "indent_style": "space",
        "indent_size": "2",
    }
    assert get_config(path / "lib" / "lol" / "foo.js") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "charset": "utf-8",
        "indent_style": "space",
        "indent_size": "2",
    }
    assert get_config(path / "Makefile") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "indent_style": "tab",
    }
    assert get_config(path / "package.json") == {
        "end_of_line": "lf",
        "insert_final_newline": "true",
        "indent_style": "space",
        "indent_size": "2",
    }


def test_good_values(filetab):
    apply_config(
        {
            "indent_style": "tab",
            "indent_size": "tab",
            "tab_width": "8",
            "charset": "latin1",
            "max_line_length": "123",
            "end_of_line": "crlf",
            "trim_trailing_whitespace": "false",
            "insert_final_newline": "false",
        },
        filetab,
    )
    assert not filetab.settings.get("tabs2spaces", bool)
    assert filetab.settings.get("indent_size", int) == 8
    assert filetab.settings.get("encoding", str) == "latin1"
    assert filetab.settings.get("max_line_length", int) == 123
    assert filetab.settings.get("line_ending", settings.LineEnding) == settings.LineEnding.CRLF
    assert not filetab.settings.get("trim_trailing_whitespace", bool)
    assert not filetab.settings.get("insert_final_newline", bool)


def test_bad_values(filetab, caplog):
    caplog.set_level(logging.WARNING)

    apply_config({"indent_style": "asd"}, filetab)
    apply_config({"indent_size": "foo"}, filetab)
    apply_config({"indent_size": "tab", "tab_width": "bar"}, filetab)
    apply_config({"charset": "ascii"}, filetab)
    apply_config({"max_line_length": "my ass"}, filetab)
    apply_config({"end_of_line": "da newline character lulz"}, filetab)
    apply_config({"trim_trailing_whitespace": "asd"}, filetab)
    apply_config({"insert_final_newline": "its late"}, filetab)
    apply_config({"foo": "123", "bar": "lol"}, filetab)

    assert [(record.levelname, record.getMessage()) for record in caplog.records] == [
        ("ERROR", "bad indent_style: 'asd'"),
        ("ERROR", "bad indent_size or tab_width: 'foo'"),
        ("ERROR", "bad indent_size or tab_width: 'bar'"),
        ("ERROR", "bad charset: 'ascii'"),
        ("ERROR", "bad max_line_length: 'my ass'"),
        ("ERROR", "bad end_of_line: 'da newline character lulz'"),
        ("ERROR", "bad trim_trailing_whitespace: 'asd'"),
        ("ERROR", "bad insert_final_newline: 'its late'"),
        ("WARNING", "editorconfig files contain unknown options: bar, foo"),
    ]


def test_encoding(tabmanager, tmp_path, mocker):
    mock = mocker.patch("porcupine.tabs._ask_encoding")
    (tmp_path / ".editorconfig").write_text("[*.latin1]\ncharset = latin1\n")
    (tmp_path / "foo.latin1").write_text("mörkö", encoding="latin1")
    tab = tabmanager.open_file(tmp_path / "foo.latin1")
    assert tab is not None
    assert tab.textwidget.get("1.0", "end").strip() == "mörkö"
    assert not mock.called
