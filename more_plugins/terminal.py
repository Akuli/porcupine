"""Run a very shitty terminal window inside Porcupine. This plugin sucks."""
# based on this: http://wiki.tcl.tk/3314
#
# FIXME: terminal isn't aware of window size
# FIXME: mouse has to be on the terminal or it doesn't receive key strokes
import subprocess
import tkinter
from tkinter import messagebox

from porcupine import get_tab_manager, menubar, tabs


def start_xterm() -> None:
    tab = tabs.Tab(get_tab_manager())
    tab.title_choices = ["Terminal"]
    content = tkinter.Frame(tab, container=True)
    content.pack(fill='both', expand=True)  # FIXME: doesn't stretch correctly?

    try:
        process = subprocess.Popen(['xterm', '-into', str(content.winfo_id())])
    except FileNotFoundError:
        messagebox.showerror(
            "xterm not found",
            "Seems like xterm is not installed. Please install it and try again.",
        )
        return

    def terminal_wants_to_exit(junk: object) -> None:
        if tab in get_tab_manager().tabs():
            get_tab_manager().close_tab(tab)

    content.bind('<Destroy>', terminal_wants_to_exit, add=True)
    tab.bind('<Destroy>', (lambda event: process.terminate()), add=True)
    get_tab_manager().add_tab(tab)


def setup() -> None:
    # FIXME: i think it's possible to run xterm in aqua? would that work here?
    if get_tab_manager().tk.call('tk', 'windowingsystem') != 'x11':
        # TODO: more noob-friendly "u have the wrong os lel" message?
        messagebox.showerror(
            "Unsupported windowing system", "Sorry, the terminal plugin only works on X11 :("
        )
        return

    menubar.get_menu("Tools").add_command(label="Terminal", command=start_xterm)
