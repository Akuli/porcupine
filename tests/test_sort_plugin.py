def test_sort_selected(filetab):
    filetab.textwidget.insert(
        "end",
        """\
foo
ccc
aaa
bbb
bar""",
    )
    filetab.textwidget.tag_add("sel", "2.0", "4.1")
    filetab.event_generate("<<Menubar:Edit/Sort Lines>>")
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == """\
foo
aaa
bbb
ccc
bar"""
    )
    assert filetab.textwidget.index("sel.first") == "2.0"
    assert filetab.textwidget.index("sel.last") == "5.0"


def test_finding_blank_line_separated_block(filetab):
    whitespace = " " * 4
    filetab.textwidget.insert(
        "end",
        f"""\
foo
{whitespace}
ccc
aaa
bbb
{whitespace}
bar""",
    )
    filetab.textwidget.mark_set("insert", "4.0")
    filetab.event_generate("<<Menubar:Edit/Sort Lines>>")
    assert filetab.textwidget.index("insert") == "4.0"
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == f"""\
foo
{whitespace}
aaa
bbb
ccc
{whitespace}
bar"""
    )


def test_just_sorting_the_whole_file(filetab):
    filetab.textwidget.insert("end", "bbb\nccc\naaa")
    filetab.textwidget.mark_set("insert", "2.0")
    filetab.event_generate("<<Menubar:Edit/Sort Lines>>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "aaa\nbbb\nccc"
