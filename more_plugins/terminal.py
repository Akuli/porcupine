# based on this: http://wiki.tcl.tk/3314
import subprocess
import tkinter
from tkinter import messagebox

from porcupine import add_action, get_tab_manager, tabs


def start_xterm():
    tab = tabs.Tab(get_tab_manager())
    tab.title = "Terminal"
    content = tkinter.Frame(tab, container=True)
    content.pack(fill='both', expand=True)

    try:
        process = subprocess.Popen(['xterm', '-into', str(content.winfo_id())])
    except FileNotFoundError:
        messagebox.showerror("xterm not found", (
            "Seems like xterm is not installed. " +
            "Please install it and try again."))
        return

    def close_if_not_closed(junk):
        if tab in get_tab_manager().tabs:
            get_tab_manager().close_tab(tab)

    # the content is destroyed when the terminal wants to exit
    content.bind('<Destroy>', close_if_not_closed, add=True)

    # the tab is destroyed when the user wants to close it
    tab.bind('<Destroy>', lambda event: process.terminate(), add=True)

    get_tab_manager().add_tab(tab)


def setup():
    # it's possible to run full X11 on a Mac, so this is better than
    # e.g. platform.system()
    if get_tab_manager().tk.call('tk', 'windowingsystem') != 'x11':
        # TODO: more noob-friendly "u have the wrong os lel" message?
        messagebox.showerror(
            "Unsupported windowing system",
            "Sorry, the terminal plugin only works on X11 :(")
        return

    add_action(start_xterm, "Tools/Terminal", ('Ctrl+Shift+T', '<Control-T>'))
