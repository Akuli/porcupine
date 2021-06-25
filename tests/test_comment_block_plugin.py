def test_comment_block_and_undo(filetab):
    filetab.textwidget.insert("1.0", "foo\nbar\nbaz")
    filetab.textwidget.tag_add("sel", "1.0", "end - 1 char")
    filetab.textwidget.event_generate("<numbersign>")  # hashtag key press
    filetab.textwidget.insert("end - 1 char", "lol")

    assert filetab.textwidget.get("1.0", "end - 1 char") == "#foo\n#bar\n#bazlol"
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "#foo\n#bar\n#baz"
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get("1.0", "end - 1 char") == "foo\nbar\nbaz"
    filetab.textwidget.edit_undo()
    assert filetab.textwidget.get("1.0", "end - 1 char") == ""


def test_partially_commented(filetab):
    filetab.textwidget.insert(
        "1.0",
        """\
We select starting from this line
# This comment is not touched at all because it appears to be hand-written
#
To start of this line, so that the plugin shouldn't see this line as selected
""",
    )
    filetab.textwidget.tag_add("sel", "1.0", "4.0")

    filetab.textwidget.event_generate("<numbersign>")
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == """\
#We select starting from this line
## This comment is not touched at all because it appears to be hand-written
#
To start of this line, so that the plugin shouldn't see this line as selected
"""
    )

    filetab.textwidget.event_generate("<numbersign>")
    assert (
        filetab.textwidget.get("1.0", "end - 1 char")
        == """\
We select starting from this line
# This comment is not touched at all because it appears to be hand-written

To start of this line, so that the plugin shouldn't see this line as selected
"""
    )
