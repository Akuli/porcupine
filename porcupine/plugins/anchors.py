import tkinter
import time
from porcupine import tabs, get_tab_manager
from porcupine.plugins import linenumbers

# Dependent on code from linenumbers.py
setup_after = ["linenumbers"]


class AnchorManager:
    def __init__(self, tab_textwidget: tkinter.Text, linenumber_instance: tkinter.Canvas) -> None:
        self.tab_textwidget = tab_textwidget
        self.linenumber_instance = linenumber_instance

        self.anchor_symbol = "¶"

        linenumber_instance.bind("<<Updated>>", self.update_linenumbers, add=True)

    def toggle_on_off(self, event):
        cursor_index = self.tab_textwidget.index("insert linestart")
        for anchor in self.tab_textwidget.mark_names():
            if anchor.startswith("anchor_") and self.tab_textwidget.index(anchor) == cursor_index:
                self.tab_textwidget.mark_unset(anchor)
                self.linenumber_instance.do_update()
                return
        self.tab_textwidget.mark_set("anchor_" + str(time.time()), "insert linestart")

        self.linenumber_instance.do_update()

    def update_linenumbers(self, event):
        """Re-draws the anchor points every time the linenumber instance updates (scroll, insertion/deletion of text)"""
        anchor_list = [
            anchor for anchor in self.tab_textwidget.mark_names() if anchor.startswith("anchor_")
        ]

        for anchorpoint in anchor_list:
            row_tag = "line_" + self.tab_textwidget.index(anchorpoint).split(".")[0]
            [row_id] = self.linenumber_instance.find_withtag(row_tag)
            row_text = self.linenumber_instance.itemcget(row_id, "text")
            self.linenumber_instance.itemconfigure(row_id, text=row_text + " " + self.anchor_symbol)

    # for jumping up
    # [mark for mark in textwidget.mark_names() if textwidget.compare(mark, "<", "insert")]


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        [linenumber_instance] = [
            child
            for child in tab.left_frame.winfo_children()
            if isinstance(child, linenumbers.LineNumbers)
        ]
        anchor = AnchorManager(tab.textwidget, linenumber_instance)
        tab.textwidget.bind("<Control-g>", anchor.toggle_on_off, add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
