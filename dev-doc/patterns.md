# Common Patterns

This file documents things that you will see all over Porcupine.
If something isn't listed here, please create an issue.


## Text Widget Locations

Tkinter uses `"line.column"` strings to represents locations in `tkinter.Text` widgets.
For example, `"12.3"` means "line 12, column 3".
**Text locations cannot be treated as floats**:
`"12.30"` means "line 12, column 30", even though as a float it would be equal to `12.3`.
Line numbers are 1-based and columns 0-based, so `"1.0"` is the start of the text widget.

Actually, `"line.column"` is only one of the many forms accepted by tkinter.
See `INDICES` in [the `text(3tk)` manual page](https://www.tcl.tk/man/tcl8.6/TkCmd/text.htm) for a full list.
Here are the most common ways to specify locations:
- `end` is **one imaginary newline character beyond** the end of the text widget
- `end - 1 char` is the end of the text widget
- `12.3 + 4 chars` goes 4 characters forward from column 3 of line 12, going to line 13 and beyond as needed.
- `insert` is cursor location (not to be confused with the `.insert()` method which adds text)
- `current` is **mouse** location
- `sel.first` and `sel.last` are the start and end of the selection.
    You will get `tkinter.TclError` for using these if nothing is selected.
- `12.0 lineend` is the end of line 12.
    It takes the start of line 12 (`12.0`) and goes to the end of that line.
    There is also `linestart`.

You can use `textwidget.index(location)` to convert a location into `"line.column"` format.

Examples:
- Get line number: `int(location.split(".")[0])` (or `int(textwidget.index(location).split(".")[0])` if not already in `"line.column"` form)
- Get column number: `int(location.split(".")[1])`
- Get line and column numbers at once: `line, column = map(int, location.split("."))`
- Count length of file in lines: `int(text.index("end - 1 char").split(".")[0])`
- Get all text in the text widget: `textwidget.get("1.0", "end - 1 char")`
- Get selected text: `textwidget.get("sel.first", "sel.last")`
- Get selected text, but always take the entire line: `text.get("sel.first linestart", "sel.first lineend")`
- Get line of text that contains cursor: `textwidget.get("insert linestart", "insert lineend")`
- Move cursor to start of file: `textwidget.mark_set("insert", "1.0")`
- Move cursor to start of line: `textwidget.mark_set("insert", "insert linestart")`
- Add newline to end of file: `textwidget.insert("end - 1 char", "\n")`
- Add character `a`, as if the user pressed the A key: `textwidget.insert("insert", "a")`


## Tests: `.update()` + `.event_generate()`

See [virtual-events.md](virtual-events.md) to understand what `.event_generate()` does.
That said, `.event_generate()` also works with physical events (as opposed to virtual events),
and that's useful for simulating key presses in tests.

For example, the `<Tab>` event runs when the user presses the tab key.
The tests of the `autocomplete` plugin do this:

```python
filetab.update()
filetab.textwidget.event_generate("<Tab>")
```

This behaves as if the user pressed the Tab key, so it should show autocompletions.

In tests, you sometimes need to add `.update()` before `.event_generate()`.
I'm not sure why.
I suspect that Tk just ignores keyboard events like `<Control-z>` when the widget is not visible yet,
and `.update()` waits until all widgets are fully loaded.

The `.update()` method is somewhat weird.
**It does not matter what widget's `.update()` you call**,
so `filetab.update()` is equivalent to `filetab.textwidget.update()` or `get_tab_manager().update()`.
