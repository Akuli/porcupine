import tkinter
import re
from tkinter import ttk
from porcupine import tabs, get_tab_manager, images, utils
from pathlib import Path
from porcupine.plugins.run.no_terminal import get_runner


setup_after = ["run"]

currently_containing_highlight: tkinter.Text | None = None


def clear_highlight_if_any() -> None:
    global currently_containing_highlight

    if currently_containing_highlight is not None and currently_containing_highlight.winfo_exists():
        currently_containing_highlight.tag_remove("debugger-highlight", "1.0", "end")
        currently_containing_highlight = None


def highlight_line(path: Path, lineno: int) -> None:
    clear_highlight_if_any()

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


def debugger_buttons_can_be_used() -> bool:
    last_line = get_runner().textwidget.get("end - 1 char linestart", "end - 1 char")
    return last_line == "(Pdb) "


debugger_buttons = []


def show_or_hide_buttons():
    if debugger_buttons_can_be_used():
        # Reversed because we pack right to left.
        for button in reversed(debugger_buttons):
            button.pack(side="left", padx=1)
    else:
        for button in debugger_buttons:
            button.pack_forget()

    get_tab_manager().after(50, show_or_hide_buttons)


def run_debugger_command(command: str) -> None:
    if debugger_buttons_can_be_used():
        get_runner().textwidget.insert("end", command)
        get_runner().textwidget.mark_set("insert", "end")
        get_runner().handle_enter_press()


def setup():
    get_tab_manager().add_filetab_callback(on_new_filetab)
    get_runner().textwidget.bind("<<OutputAdded>>", on_output_added, add=True)

    step_over_button = ttk.Label(get_runner().button_frame, image=images.get("step_over"), cursor="hand2")
    step_over_button.bind("<Button-1>", (lambda e: run_debugger_command("next")), add=True)
    utils.set_tooltip(step_over_button, "Run to next statement")
    debugger_buttons.append(step_over_button)

    step_into_button = ttk.Label(get_runner().button_frame, image=images.get("step_into"), cursor="hand2")
    step_into_button.bind("<Button-1>", (lambda e: run_debugger_command("step")), add=True)
    utils.set_tooltip(step_into_button, "Step into function")
    debugger_buttons.append(step_into_button)

    show_or_hide_buttons()
