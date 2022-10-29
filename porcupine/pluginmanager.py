"""Enable and disable Porcupine plugins."""
from __future__ import annotations

import ast
import importlib.util
import logging
import re
import tkinter
from functools import partial
from tkinter import ttk
from typing import List

from porcupine import get_main_window, pluginloader, textutils, utils
from porcupine.settings import global_settings

log = logging.getLogger(__name__)

dialog: tkinter.Toplevel | None = None


def get_docstring(module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
        docstring = str(module.__doc__ or "").strip()
        if docstring:
            return docstring
    except Exception:  # importing runs arbitrary code
        pass

    # importing won't work (broken plugin has been disabled)
    # but maybe we can parse the source file without executing it?
    spec = importlib.util.find_spec(module_name)
    if spec is not None and spec.origin is not None and spec.has_location:
        try:
            with open(spec.origin, "r") as file:
                ast_module = ast.parse(file.read())
        except (OSError, SyntaxError):
            pass
        else:
            docstring = (ast.get_docstring(ast_module) or "").strip()
            if docstring:
                return docstring

    return "(no description available)"


DIALOG_WIDTH = 850
DIALOG_HEIGHT = 350


class PluginDialogContent:
    def __init__(self, master: tkinter.Misc) -> None:
        self.content_frame = ttk.Frame(master)

        panedwindow = utils.PanedWindow(self.content_frame, orient="horizontal")
        panedwindow.pack(side="top", fill="both", expand=True)
        self._plz_restart_label = ttk.Label(self.content_frame)
        self._plz_restart_label.pack(side="bottom", fill="x")

        column_sizes = (120, 150, 180)

        left_side = ttk.Frame(panedwindow, padding=5)
        right_side = ttk.Frame(panedwindow, padding=5, width=10000)  # to shrink left_side
        panedwindow.add(left_side, minsize=sum(column_sizes))
        panedwindow.add(right_side, minsize=300)

        self.treeview = ttk.Treeview(
            left_side, show="headings", columns=("name", "type", "status"), selectmode="extended"
        )
        self.treeview.bind("<<TreeviewSelect>>", self._on_select, add=True)

        scrollbar = ttk.Scrollbar(left_side, command=self.treeview.yview)
        self.treeview.config(yscrollcommand=scrollbar.set)

        self._search_var = tkinter.StringVar(value="Filter by name, type or status...")
        search_entry = ttk.Entry(left_side, textvariable=self._search_var)
        search_entry.bind(
            "<FocusIn>", (lambda event: search_entry.selection_range(0, "end")), add=True
        )
        self._search_var.trace_add("write", self._search)

        search_entry.pack(side="bottom", fill="x", pady=(5, 0))
        self.treeview.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for index, width in enumerate(column_sizes):
            self.treeview.column(index, width=width, minwidth=width)

        for index, header_title in enumerate(["Name", "Type", "Status"]):
            self.treeview.heading(index, text=header_title)

        self._insert_data()
        self._update_plz_restart_label()

        # Must pack everything else before description label so that if
        # description is very long, it doesn't cover up other things
        self._title_label = ttk.Label(right_side, font=("", 15, "bold"))
        self._title_label.pack(side="top", pady=(0, 10))
        button_frame = ttk.Frame(right_side)
        button_frame.pack(side="bottom", fill="x")

        self.enable_button = ttk.Button(
            button_frame, text="Enable", command=partial(self._set_enabled, True), state="disabled"
        )
        self.enable_button.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.disable_button = ttk.Button(
            button_frame,
            text="Disable",
            command=partial(self._set_enabled, False),
            state="disabled",
        )
        self.disable_button.pack(side="left", expand=True, fill="x", padx=(5, 0))

        self.description = textutils.create_passive_text_widget(right_side)
        self._set_description(
            "No plugin selected. Select one or more from the list to disable or enable it."
        )
        self.description.pack(fill="both", expand=True)

    def _set_description(self, text: str) -> None:
        self.description.config(state="normal")
        self.description.delete("1.0", "end")
        self.description.insert("1.0", text)
        self.description.config(state="disabled")

    def _insert_data(self) -> None:
        for info in sorted(pluginloader.plugin_infos, key=(lambda info: info.name)):
            self.treeview.insert("", "end", id=info.name)
            self._update_row(info)

    def _search(self, *junk: object) -> None:
        search_regex = ".*".join(map(re.escape, self._search_var.get()))
        index = 0
        for name in sorted(info.name for info in pluginloader.plugin_infos):
            if any(
                re.search(search_regex, v, flags=re.IGNORECASE)
                for v in self.treeview.item(name, "values")
            ):
                self.treeview.move(name, "", index)
                index += 1
            else:
                self.treeview.detach(name)

    def _update_row(self, info: pluginloader.PluginInfo) -> None:
        if info.came_with_porcupine:
            how_it_got_installed = "Came with Porcupine"
        else:
            how_it_got_installed = "You installed this"

        disable_list = global_settings.get("disabled_plugins", List[str])
        if (
            info.status == pluginloader.Status.DISABLED_BY_SETTINGS
            and info.name not in disable_list
        ):
            message = "Will be enabled upon restart"
        elif info.status != pluginloader.Status.DISABLED_BY_SETTINGS and info.name in disable_list:
            message = "Will be disabled upon restart"
        else:
            message = {
                # it should be impossible to get here with LOADING status
                pluginloader.Status.ACTIVE: "Active",
                pluginloader.Status.DISABLED_BY_SETTINGS: "Disabled",
                pluginloader.Status.DISABLED_ON_COMMAND_LINE: "Disabled on command line",
                pluginloader.Status.IMPORT_FAILED: "Importing failed",
                pluginloader.Status.SETUP_FAILED: "Setup failed",
                pluginloader.Status.CIRCULAR_DEPENDENCY_ERROR: "Circular dependency",
            }[info.status]

        self.treeview.item(info.name, values=(info.name, how_it_got_installed, message))

    def _update_plz_restart_label(self) -> None:
        statuses = (self.treeview.item(name, "values")[-1] for name in self.treeview.get_children())
        if any(status.endswith("upon restart") for status in statuses):
            self._plz_restart_label.config(text="Please restart Porcupine to apply the changes.")
        else:
            self._plz_restart_label.config(text="")

    def _get_selected_infos(self) -> list[pluginloader.PluginInfo]:
        selection = self.treeview.selection()
        infos = [info for info in pluginloader.plugin_infos if info.name in selection]
        assert len(infos) == len(selection)
        return infos

    def _on_select(self, junk: object = None) -> None:
        infos = self._get_selected_infos()
        disable_list = global_settings.get("disabled_plugins", List[str])

        if len(infos) == 1:
            info = infos[0]
            if info.status == pluginloader.Status.IMPORT_FAILED:
                text = f"Importing the plugin failed.\n\n{info.error}"
            elif info.status == pluginloader.Status.SETUP_FAILED:
                text = f"Calling the plugin's setup() function failed.\n\n{info.error}"
            elif info.status == pluginloader.Status.CIRCULAR_DEPENDENCY_ERROR:
                assert info.error is not None
                text = info.error
            else:
                text = get_docstring(f"porcupine.plugins.{info.name}")
                # get rid of single newlines
                text = re.sub(r"(.)\n(.)", r"\1 \2", text)

            self._title_label.config(text=info.name)
            self._set_description(text)

        else:
            self._title_label.config(text="")
            self._set_description(f"{len(infos)} plugins selected.")

        can_enable = any(info.name in disable_list for info in infos)
        can_disable = any(info.name not in disable_list for info in infos)
        self.enable_button.config(state=("normal" if can_enable else "disabled"))
        self.disable_button.config(state=("normal" if can_disable else "disabled"))

    def _set_enabled(self, they_become_enabled: bool) -> None:
        infos = self._get_selected_infos()

        disabled = set(global_settings.get("disabled_plugins", List[str]))
        if they_become_enabled:
            disabled -= {info.name for info in infos}
        else:
            disabled |= {info.name for info in infos}
        global_settings.set("disabled_plugins", list(disabled))

        for info in infos:
            if info.name not in disabled and pluginloader.can_setup_while_running(info):
                pluginloader.setup_while_running(info)
            self._update_row(info)

        self._on_select()
        self._update_plz_restart_label()


def show_dialog() -> None:
    global dialog
    if dialog is not None and dialog.winfo_exists():
        dialog.lift()
        dialog.focus()
    else:
        dialog = create_dialog()[0]


def create_dialog() -> tuple[tkinter.Toplevel, PluginDialogContent]:
    dialog = tkinter.Toplevel()
    dialog.title("Porcupine Plugin Manager")
    content = PluginDialogContent(dialog)
    content.content_frame.pack(fill="both", expand=True)
    dialog.transient(get_main_window())
    dialog.geometry(f"{DIALOG_WIDTH}x{DIALOG_HEIGHT}")
    dialog.minsize(DIALOG_WIDTH, DIALOG_HEIGHT)
    return (dialog, content)  # content returned for tests
