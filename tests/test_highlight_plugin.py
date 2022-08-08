import subprocess
import sys

from pygments.lexers import PythonLexer, YamlLexer, TclLexer, BashLexer


def test_pygments_deleting_bug(filetab):
    def tag_ranges(tag):
        return list(map(str, filetab.textwidget.tag_ranges(tag)))

    filetab.settings.set("syntax_highlighter", "pygments")
    filetab.settings.set("pygments_lexer", PythonLexer)
    filetab.textwidget.insert("1.0", "return None")
    assert tag_ranges("Token.Keyword") == ["1.0", "1.6"]
    assert tag_ranges("Token.Keyword.Constant") == ["1.7", "1.11"]
    assert tag_ranges("Token.Literal.String.Double") == []

    filetab.textwidget.insert("1.0", '"')
    filetab.update()
    assert tag_ranges("Token.Keyword") == []
    assert tag_ranges("Token.Keyword.Constant") == []
    assert tag_ranges("Token.Literal.String.Double") == ["1.0", "1.12"]

    filetab.textwidget.delete("1.0")
    filetab.update()
    assert tag_ranges("Token.Keyword") == ["1.0", "1.6"]
    assert tag_ranges("Token.Keyword.Constant") == ["1.7", "1.11"]
    assert tag_ranges("Token.Literal.String.Double") == []


def test_pygments_yaml_highlighting(filetab, tmp_path):
    filetab.settings.set("syntax_highlighter", "pygments")
    filetab.settings.set("pygments_lexer", YamlLexer)
    filetab.textwidget.insert("1.0", '"lol"')
    filetab.update()
    assert filetab.textwidget.tag_names("1.2") == ("Token.Literal.String",)


def test_pygments_tcl_bug(filetab, tmp_path):
    filetab.settings.set("syntax_highlighter", "pygments")
    filetab.settings.set("pygments_lexer", TclLexer)
    filetab.textwidget.replace("1.0", "end - 1 char", "# bla\n" * 50)
    filetab.textwidget.see("end")
    filetab.textwidget.insert("end - 1 char", "a")
    filetab.update()
    for lineno in range(1, 51):
        assert filetab.textwidget.tag_names(f"{lineno}.3") == ("Token.Comment",)


def test_pygments_last_line_bug(filetab, tmp_path):
    filetab.settings.set("syntax_highlighter", "pygments")
    filetab.settings.set("pygments_lexer", BashLexer)
    filetab.textwidget.delete("1.0", "end")  # Delete inserted trailing newline
    filetab.textwidget.insert("1.0", "# This is a comment")
    filetab.update()
    assert filetab.textwidget.tag_names("1.5") == ("Token.Comment.Single",)


# I currently don't think the tree-sitter highlighter needs lots of tests.
# If it doesn't work, it's usually quite obvious after using it a while.
#
# That said, it comes with a couple fragile things:
#    - Unzipping and loading the correct binary file on each platform
#    - The dumping script, used only when configuring the plugin
#
# These need testing, and this test conveniently tests them both.
def test_tree_sitter_dump(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello')")
    output = subprocess.check_output(
        [sys.executable, "scripts/tree-sitter-dump.py", "python", str(tmp_path / "hello.py")],
        text=True,
    )

    expected_output = """
type=module text="print('hello')"
  type=expression_statement text="print('hello')"
    type=call text="print('hello')"
      type=identifier text='print'
      type=argument_list text="('hello')"
        type=( text='('
        type=string text="'hello'"
          type=" text="'"
          type=" text="'"
        type=) text=')'
    """
    assert output.strip() == expected_output.strip()
