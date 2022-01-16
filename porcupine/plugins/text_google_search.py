"""Search selected text on Google."""

import tkinter as tk
from porcupine import menubar, tabs
import webbrowser
import urllib.parse

def google_search(tab: tabs.FileTab) -> None:
    selected_text = tab.textwidget.get("sel.first", "sel.last")
    url = "https://www.google.com/search?q={}".format(urllib.parse.quote_plus(selected_text))
    webbrowser.open_new_tab(url)

def setup() -> None:
    menubar.add_filetab_command("Tools/Search selected text on Google", google_search)
