import tkinter
import re
from porcupine import tabs, get_tab_manager
from pathlib import Path
from porcupine.plugins.run.no_terminal import get_runner, open_file_with_line_number


setup_after = ["run"]

currently_containing_highlight: tkinter.Text | None = None


def clear_highlight_if_any() -> None:
    global currently_containing_highlight

    if currently_containing_highlight is not None and currently_containing_highlight.winfo_exists():
        currently_containing_highlight.tag_remove("debugger-highlight", "1.0", "end")
        currently_containing_highlight = None


def highlight_line(path: Path, lineno: int) -> None:
    clear_highlight_if_any()

    # focus_existing=False needed to keep focus in debugger/output area.
    #tab = get_tab_manager().open_file(path, focus_existing=False)
    tab = get_tab_manager().open_file(path)
    tab.textwidget.mark_set("insert", f"{lineno}.0")
    tab.textwidget.tag_add("debugger-highlight", f"{lineno}.0", f"{lineno+1}.0")
    tab.textwidget.see("insert")

    global currently_containing_highlight
    currently_containing_highlight = tab.textwidget


def on_output_added(event):
    # If not in a debugger, we shouldn't highlight anything
    if event.widget.get("end - 7 chars", "end - 1 char") != "(Pdb) ":
        clear_highlight_if_any()
        return

    last_few_lines = event.widget.get("end - 1 char linestart - 2 lines", "end - 1 char")
    match = re.fullmatch(r"> ([^()\n]+)\((\d+)\).*\n-> .*\n\(Pdb\) ", last_few_lines)
    if match is not None:
        # Debugger moved into new file/line
        filename, lineno = match.groups()
        highlight_line(Path(filename), int(lineno))
        # TODO: while this works, the 50ms timeout is not very elegant
        event.widget.after(50, lambda: event.widget.focus())


def on_new_filetab(tab: tabs.FileTab) -> None:
    # TODO: get rid of hard-coded color
    tab.textwidget.tag_config("debugger-highlight", background="green")
    tab.textwidget.tag_lower("debugger-highlight", "sel")


def setup():
    get_tab_manager().add_filetab_callback(on_new_filetab)
    get_runner().textwidget.bind("<<OutputAdded>>", on_output_added, add=True)
