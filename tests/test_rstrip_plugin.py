def test_rstrip(filetab):
    filetab.textwidget.insert("end", 'print("hello")  ')
    filetab.update()
    filetab.event_generate("<Return>")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == 'print("hello")\n'
