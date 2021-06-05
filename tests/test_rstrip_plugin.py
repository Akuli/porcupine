def test_rstrip(filetab):
    filetab.textwidget.insert("end", 'print("hello")  ')
    filetab.update()
    filetab.event_generate("<Return>")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == 'print("hello")\n'

    # ctrl+enter should not wipe trailing whitespace
    filetab.textwidget.delete("1.0", "end")
    filetab.textwidget.insert("end", 'print("hello")  ')
    filetab.update()
    if filetab.tk.eval("tk windowingsystem") == "aqua":
        filetab.event_generate("<Command-Return>")
    else:
        filetab.event_generate("<Control-Return>")
    filetab.update()
    assert filetab.textwidget.get("1.0", "end - 1 char") == 'print("hello")  \n'
