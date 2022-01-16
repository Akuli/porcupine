"""Search selected text on Google."""

import tkinter as tk
from porcupine import menubar, tabs
import webbrowser

def google_search(tab: tabs.FileTab) -> None:
    try:
        selected_text_tuple = tab.textwidget.tag_ranges(tk.SEL)
        # Check if text is selected to search on Google
        if len(selected_text_tuple)>0:
            selected_text = tab.textwidget.get(*selected_text_tuple)
            url = "https://www.google.com/search?q={}".format(selected_text)
            webbrowser.open_new_tab(url)
        else:
            tk.messagebox.showwarning("Warning","Please select text!")
    except:
        tk.messagebox.showerror("Error", "Something went wrong!")

def setup() -> None:
    menubar.add_filetab_command("Tools/Google Search", google_search)
