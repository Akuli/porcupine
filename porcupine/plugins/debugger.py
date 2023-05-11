import tkinter
import re
from porcupine import tabs, get_tab_manager
from pathlib import Path
from porcupine.plugins.run.no_terminal import get_runner, open_file_with_line_number


setup_after = ["run"]

currently_containing_highlight: tkinter.Text | None = None


def highlight_line(path: Path, lineno: int) -> None:
    print("HIGHLIGHT", path, lineno)
    global currently_containing_highlight

    if currently_containing_highlight is not None and currently_containing_highlight.winfo_exists():
        currently_containing_highlight.tag_remove("debugger-highlight", "1.0", "end")

    tab = get_tab_manager().open_file(path)
    tab.textwidget.mark_set("insert", f"{lineno}.0")
    tab.textwidget.tag_add("debugger-highlight", f"{lineno}.0", f"{lineno+1}.0")
    tab.textwidget.see("insert")
    currently_containing_highlight = tab.textwidget


def on_output_added(event):
    # Pseudo-optimization: regexes could be slow, let's skip them in the common case
    if event.widget.get("end - 7 chars", "end - 1 char") != "(Pdb) ":
        return

    last_few_lines = event.widget.get("end - 1 char linestart - 2 lines", "end - 1 char")
    print(repr(last_few_lines))

    match = re.fullmatch(r"> ([^()\n]+)\((\d+)\).*\n-> .*\n\(Pdb\) ", last_few_lines)
    if match is None:
        return

    filename, lineno = match.groups()
    highlight_line(Path(filename), int(lineno))
    event.widget.focus()


def on_new_filetab(tab: tabs.FileTab) -> None:
    # TODO: get rid of hard-coded color
    tab.textwidget.tag_config("debugger-highlight", background="green")
    tab.textwidget.tag_lower("debugger-highlight", "sel")


def setup():
    get_tab_manager().add_filetab_callback(on_new_filetab)
    get_runner().textwidget.bind("<<OutputAdded>>", on_output_added, add=True)
