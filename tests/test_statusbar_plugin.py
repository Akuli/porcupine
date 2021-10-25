from porcupine.plugins.statusbar import StatusBar


def test_reload_warning(filetab, tmp_path):
    [statusbar] = [w for w in filetab.bottom_frame.winfo_children() if isinstance(w, StatusBar)]

    filetab.path = tmp_path / "lol.py"
    filetab.save()

    filetab.path.write_text("hello")
    assert filetab.reload()
    filetab.update()
    assert statusbar.path_label["text"].endswith("lol.py")
    assert statusbar.path_label["foreground"] == ""

    filetab.textwidget.insert("1.0", "asdf")
    filetab.path.write_text("foo")
    assert filetab.reload()
    filetab.update()
    # Ctrl+Z or Command+Z
    assert "Press " in statusbar.path_label["text"]
    assert "Z to get your changes back" in statusbar.path_label["text"]
    assert statusbar.path_label["foreground"] != ""

    filetab.save()  # user is happy with whatever is currently in text widget
    assert statusbar.path_label["text"].endswith("lol.py")
    assert statusbar.path_label["foreground"] == ""


def select(filetab, start, end):
    filetab.textwidget.tag_remove("sel", "1.0", "end")
    filetab.textwidget.tag_add("sel", start, end)
    filetab.update()


def test_selection(filetab):
    [statusbar] = [w for w in filetab.bottom_frame.winfo_children() if isinstance(w, StatusBar)]

    filetab.textwidget.insert("1.0", "b öa\n" * 4)
    filetab.textwidget.mark_set("insert", "1.2")
    filetab.update()
    assert statusbar.selection_label["text"] == "Line 1, column 2"

    select(filetab, "1.2", "1.3")
    assert (
        statusbar.selection_label["text"]
        == "Unicode character U+F6: LATIN SMALL LETTER O WITH DIAERESIS"
    )

    select(filetab, "1.3", "1.4")
    assert statusbar.selection_label["text"] == "ASCII character 97 (hex 61)"

    select(filetab, "1.2", "1.4")
    assert statusbar.selection_label["text"] == "2 characters selected"

    select(filetab, "1.2", "2.2")
    assert statusbar.selection_label["text"] == "5 characters (2 words) on 2 lines selected"

    select(filetab, "1.2", "2.4")
    filetab.update()
    assert statusbar.selection_label["text"] == "7 characters (3 words) on 2 lines selected"

    # selecting to end of line doesn't mean next line (consistent with indent_block plugin)
    select(filetab, "1.2", "3.0")
    assert statusbar.selection_label["text"] == "8 characters (3 words) on 2 lines selected"

    select(filetab, "1.2", "3.1")
    assert statusbar.selection_label["text"] == "9 characters (4 words) on 3 lines selected"

    filetab.textwidget.tag_remove("sel", "1.0", "end")
    filetab.update()
    assert statusbar.selection_label["text"] == "Line 1, column 2"
