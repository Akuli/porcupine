"""An interactive Python prompt in the Porcupine process, accessible from the "Run" menu.

Unlike a normal ">>>" prompt, the one here lets you run commands that affect
the current Porcupine instance. You can e.g. access the opened tabs.
For example, this sets the color of the last tab:

    >>> get_tab_manager().tabs()[-1].textwidget['bg'] = 'green'

This plugin is somewhat buggy and annoying to use, but it's still occasionally
useful when developing Porcupine.
"""

import contextlib
import io
import queue
import tkinter
import traceback
from tkinter import ttk
from typing import Any

from porcupine import get_tab_manager, menubar, tabs, textutils

# In "Run" menu, get the important stuff first
setup_after = ["run"]


class PromptTab(tabs.Tab):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.title_choices = ["Porcupine Debug Prompt"]
        self.namespace = {}
        exec("from porcupine import *", self.namespace)

        self.textwidget = tkinter.Text(self, width=1, height=1)
        self.textwidget.pack(side="left", fill="both", expand=True)
        self.textwidget.mark_set("output_end", "end")
        self.textwidget.mark_gravity("output_end", "left")
        self.show(">>> from porcupine import *\n>>> ")
        try:
            textutils.use_pygments_theme(self.textwidget)
        except AttributeError:
            textutils.use_pygments_tags(self.textwidget)

        self.scrollbar = ttk.Scrollbar(self)
        self.scrollbar.pack(side="left", fill="y")
        self.textwidget.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.textwidget.yview)

        self.to_interpreter_queue = queue.Queue()
        self.from_interpreter_queue = queue.Queue()
        self.bind("<Destroy>", (lambda event: self.to_interpreter_queue.put(None)), add=True)
        self.bind("<<TabSelected>>", (lambda event: self.textwidget.focus()), add=True)
        self.textwidget.bind("<Return>", self.on_enter_key, add=True)

    def show(self, string):
        self.textwidget.insert("end - 1 char", string)
        self.textwidget.mark_set("output_end", "end - 1 char")
        self.textwidget.mark_set("insert", "end - 1 char")
        self.textwidget.see("insert")

    def on_focus(self) -> None:
        self.textwidget.focus_set()

    def on_enter_key(self, event=None) -> None:
        code_string = self.textwidget.get("output_end", "end - 1 char")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = compile(code_string, "<prompt>", "single")
                exec(code, self.namespace)
            except Exception:
                traceback.print_exc()
        self.show(f"\n{out.getvalue()}>>> ")
        return "break"


def start_prompt() -> None:
    for tab in get_tab_manager().tabs():
        if isinstance(tab, PromptTab):
            get_tab_manager().select(tab)
            return
    get_tab_manager().add_tab(PromptTab(get_tab_manager()))


def setup() -> None:
    menubar.get_menu("Run").add_separator()
    menubar.get_menu("Run").add_command(label="Porcupine debug prompt", command=start_prompt)
