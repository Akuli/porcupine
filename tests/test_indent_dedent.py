import platform

import pytest

from porcupine.plugins.autoindent import ALT_FLAG

_FUNNY = """\
def foo(
    x,
     y
"""
_DEDENTED = """\
def foo(
    x,
    y
"""
_BEFORE_Y = "3.5"
_AFTER_Y = "3.6"


# issue 65
def test_dedent_when_misaligned(filetab):
    filetab.settings.set("indent_size", 4)
    filetab.settings.set("tabs2spaces", True)
    filetab.update()

    filetab.textwidget.insert("end", _FUNNY)
    assert filetab.textwidget.dedent(_BEFORE_Y)
    assert filetab.textwidget.get("1.0", "end - 1 char") == _DEDENTED


# issue 74
def test_doesnt_delete_stuff_far_away_from_cursor(filetab):
    filetab.settings.set("indent_size", 4)
    filetab.settings.set("tabs2spaces", True)
    filetab.update()

    filetab.textwidget.insert("end", _FUNNY)
    assert not filetab.textwidget.dedent(_AFTER_Y)
    assert filetab.textwidget.get("1.0", "end - 1 char") == _FUNNY


def test_dedent_start_of_line(filetab):
    filetab.settings.set("indent_size", 4)

    for tabs2spaces in [True, False]:
        filetab.settings.set("tabs2spaces", tabs2spaces)
        filetab.update()

        filetab.textwidget.insert("end", (" " * 4 if tabs2spaces else "\t") + "a")
        assert filetab.textwidget.dedent("1.0")
        assert filetab.textwidget.get("1.0", "end - 1 char") == "a"
        assert not filetab.textwidget.dedent("1.0")
        assert filetab.textwidget.get("1.0", "end - 1 char") == "a"
        filetab.textwidget.delete("1.0", "end")


def test_indent_block_plugin(filetab):
    filetab.textwidget.insert(
        "1.0",
        """\
foo
bar
biz
baz""",
    )
    filetab.textwidget.tag_add("sel", "2.1", "3.2")
    filetab.textwidget.event_generate("<Tab>")
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == """\
foo
    bar
    biz
baz"""
    )
    assert list(map(str, filetab.textwidget.tag_ranges("sel"))) == ["2.0", "4.0"]

    # shift-tab is platform specific, see utils.bind_tab_key
    [shift_tab] = [
        key for key in filetab.textwidget.bind() if key.endswith("Tab>") and key != "<Key-Tab>"
    ]
    filetab.textwidget.event_generate(shift_tab)
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == """\
foo
bar
biz
baz"""
    )
    assert list(map(str, filetab.textwidget.tag_ranges("sel"))) == ["2.0", "4.0"]


def test_autoindent(filetab):
    indent = " " * 4
    filetab.textwidget.insert("end", f"{indent}if blah:  # comment")
    filetab.textwidget.event_generate("<Return>")
    filetab.update()
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == f"{indent}if blah:  # comment\n{indent}{indent}"
    )


# FIXME: figure out how to do this on mac
@pytest.mark.skipif(platform.system() == "Darwin", reason="I don't have a mac")
def test_shift_enter_and_alt_enter(filetab):
    # See issue #404 (not the HTTP status, lol)
    indent = " " * 4
    filetab.textwidget.insert("1.0", f"{indent}if blah:  # comment")
    filetab.textwidget.event_generate("<Shift-Return>")  # just like <Return>
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char").endswith(f"\n{indent}{indent}")

    filetab.textwidget.delete("1.0 lineend", "end")
    # Unfortunately event_generate('<Alt-Return>') doesn't work, need to trust that ALT_FLAG is correct
    filetab.textwidget.event_generate("<Return>", state=ALT_FLAG)
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char").endswith(f"\n{indent}")


def test_dedent_on_closing_paren(filetab):
    filetab.textwidget.insert("1.0", "print(\n    foo\n    ")
    filetab.textwidget.event_generate("<Key>", keysym="parenright")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "print(\n    foo\n)"


def test_space_inside_braces_bug(filetab):
    filetab.textwidget.insert("1.0", "( aa ")
    filetab.textwidget.event_generate("<Key>", keysym="parenright")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "( aa )"


def test_double_dedent_bug(filetab):
    indent = " " * 4
    filetab.textwidget.insert("end", f"{indent}{indent}return foo")
    filetab.textwidget.event_generate("<Return>")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == f"{indent}{indent}return foo\n{indent}"
    filetab.textwidget.event_generate("<Key>", keysym="parenright")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == f"{indent}{indent}return foo\n{indent})"


def test_space_in_tabs_file_bug(filetab, tmp_path):
    filetab.settings.set("tabs2spaces", False)
    filetab.textwidget.insert("end", "    a")
    filetab.textwidget.mark_set("insert", "1.2")

    # Backspacing one char at a time is annoying, but it should be, since
    # someone is using tabs when they should be using spaces, and you should
    # be mad at them.
    filetab.textwidget.event_generate("<<Dedent>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "   a"
    filetab.textwidget.event_generate("<<Dedent>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "  a"
    filetab.textwidget.event_generate("<<Dedent>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == " a"
    filetab.textwidget.event_generate("<<Dedent>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "a"


def test_dedent_blank_line_in_tabs_file_bug(filetab):
    filetab.settings.set("tabs2spaces", False)
    filetab.textwidget.insert("1.0", "\tfoo\n\n\tbar")
    filetab.textwidget.tag_add("sel", "1.0", "end - 1 char")
    if filetab.tk.eval("tk windowingsystem") == "x11":
        # even though the event keysym says Left, holding down the right
        # shift and pressing tab also works :D
        shift_tab = "<ISO_Left_Tab>"
    else:
        shift_tab = "<Shift-Tab>"
    filetab.textwidget.event_generate(shift_tab)
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo\n\nbar"


@pytest.fixture
def check_autoindents(filetab, tmp_path):
    def check(filename, input_commands, output):
        filetab.save_as(tmp_path / filename)
        for command in input_commands.strip().split("\n"):
            while command.startswith("<DEDENT>"):
                filetab.textwidget.event_generate("<<Dedent>>")
                filetab.update()
                command = command[8:]

            filetab.textwidget.insert("insert", command)
            filetab.textwidget.event_generate("<Return>")
            filetab.update()

        assert filetab.textwidget.get("1.0", "end").strip() == output.strip()

    return check


def test_markdown_autoindent(check_autoindents):
    check_autoindents(
        "hello.md",
        """
1. Lol and
wat.
- Foo and
bar and
baz.
End of list
""",
        """
1. Lol and
    wat.
- Foo and
    bar and
    baz.
End of list
""",
    )


def test_shell_autoindent(check_autoindents):
    check_autoindents(
        "loll.sh",
        """
case foo in
bla*)
echo lol
;;
*)
if foo; then
bar
<DEDENT>else
exit
fi
<DEDENT><DEDENT>esac
while [ 1 == 2 ]; do
blah
<DEDENT>done
for thing in a b c; do
echo $thing
<DEDENT>done
""",
        """
case foo in
    bla*)
        echo lol
        ;;
    *)
        if foo; then
            bar
        else
            exit
        fi
esac
while [ 1 == 2 ]; do
    blah
done
for thing in a b c; do
    echo $thing
done
""",
    )
