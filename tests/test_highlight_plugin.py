from pygments.lexers import PythonLexer


def test_deleting_bug(filetab):
    def tag_ranges(tag):
        return list(map(str, filetab.textwidget.tag_ranges(tag)))

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


def test_yaml_highlighting(filetab, tmp_path):
    filetab.path = tmp_path / "foo.yml"
    filetab.save()
    filetab.textwidget.insert("1.0", '"lol"')
    filetab.update()
    assert filetab.textwidget.tag_names("1.2") == ("Token.Literal.String",)


def test_tcl_bug(filetab, tmp_path):
    filetab.path = tmp_path / "foo.tcl"
    filetab.save()
    filetab.textwidget.replace("1.0", "end - 1 char", "# bla\n" * 50)
    filetab.textwidget.see("end")
    filetab.textwidget.insert("end - 1 char", "a")
    filetab.update()
    for lineno in range(1, 51):
        assert filetab.textwidget.tag_names(f"{lineno}.3") == ("Token.Comment",)


def test_last_line_bug(filetab, tmp_path):
    filetab.path = tmp_path / "foo.sh"
    filetab.save()
    filetab.textwidget.delete("1.0", "end")  # Delete inserted trailing newline
    filetab.textwidget.insert("1.0", "# This is a comment")
    filetab.update()
    assert filetab.textwidget.tag_names("1.5") == ("Token.Comment.Single",)
