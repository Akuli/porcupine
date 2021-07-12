def test_backspace_in_beginning_of_file(filetab):
    filetab.textwidget.insert("end", "a")
    filetab.textwidget.mark_set("insert", "1.0")
    filetab.textwidget.event_generate("<BackSpace>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == "a"

    filetab.textwidget.tag_add("sel", "1.0", "1.1")
    filetab.textwidget.event_generate("<BackSpace>")
    assert filetab.textwidget.get("1.0", "end - 1 char") == ""
