"""Enable and disable Porcupine plugins."""
import ast
import importlib.util
import logging
import re
import tkinter
from tkinter import ttk
from typing import List

from porcupine import (get_main_window, menubar, pluginloader, settings,
                       textwidget)

log = logging.getLogger(__name__)


def get_docstring(module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
        docstring = str(module.__doc__ or '').strip()
        if docstring:
            return docstring
    except Exception:   # importing runs arbitrary code
        pass

    # importing won't work (broken plugin has been disabled)
    # but maybe we can parse the source file without executing it?
    spec = importlib.util.find_spec(module_name)
    if spec is not None and spec.origin is not None and spec.has_location:
        try:
            with open(spec.origin, 'r') as file:
                ast_module = ast.parse(file.read())
        except (OSError, SyntaxError):
            pass
        else:
            docstring = (ast.get_docstring(ast_module) or '').strip()
            if docstring:
                return docstring

    return '(no description available)'


DIALOG_WIDTH = 800
DIALOG_HEIGHT = 300


class PluginDialogContent:

    def __init__(self, master: tkinter.Misc) -> None:
        self.content = ttk.Frame(master)

        panedwindow = ttk.Panedwindow(self.content, orient='horizontal')
        panedwindow.pack(side='top', fill='both', expand=True)
        self._plz_restart_label = ttk.Label(self.content)
        self._plz_restart_label.pack(side='bottom', fill='x')

        left_side = ttk.Frame(panedwindow)
        right_side = ttk.Frame(panedwindow)
        panedwindow.add(left_side)
        panedwindow.add(right_side)

        self._treeview = ttk.Treeview(
            left_side,
            show='headings',
            columns=('name', 'type', 'status'),
            selectmode='browse',
        )
        self._treeview.pack(side='top', fill='both', expand=True)
        self._treeview.bind('<<TreeviewSelect>>', self._on_select, add=True)

        for index, width in enumerate([100, 150, 180]):
            self._treeview.column(index, width=width, minwidth=width)

        self._treeview.heading(0, text="Name")
        self._treeview.heading(1, text="Type")
        self._treeview.heading(2, text="Status")
        self._insert_data()

        # Must pack everything else before description label so that if
        # description is very long, it doesn't cover up other things
        self._title_label = ttk.Label(right_side, font=('', 15, 'bold'))
        self._title_label.pack(side='top', pady=5)
        self._enable_disable_button = ttk.Button(
            right_side, text="Enable", command=self._toggle_enabled, state='disabled')
        self._enable_disable_button.pack(side='bottom')

        self._description = textwidget.create_passive_text_widget(right_side)
        self._description.config(state='normal')
        self._description.insert('1.0', "Please select a plugin.")
        self._description.config(state='disabled')
        self._description.pack(fill='both', expand=True)

        # I had some trouble getting this to work. With after_idle, this makes
        # the left side invisibly small. With 50ms timeout, it still happened
        # sometimes.
        panedwindow.after(100, lambda: panedwindow.sashpos(0, round(0.7*DIALOG_WIDTH)))

    def _insert_data(self) -> None:
        for info in sorted(pluginloader.plugin_infos, key=(lambda info: info.name)):
            self._treeview.insert('', 'end', id=info.name)
            self._update_row(info)
        self._update_plz_restart_label()

    def _update_row(self, info: pluginloader.PluginInfo) -> None:
        if info.came_with_porcupine:
            how_it_got_installed = "Came with Porcupine"
        else:
            how_it_got_installed = "You installed this"

        disable_list = settings.get('disabled_plugins', List[str])
        if info.status == pluginloader.Status.DISABLED_BY_SETTINGS and info.name not in disable_list:
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

        self._treeview.item(info.name, values=(info.name, how_it_got_installed, message))

    def _update_plz_restart_label(self) -> None:
        statuses = (
            self._treeview.item(name, 'values')[-1]
            for name in self._treeview.get_children()
        )
        if any(status.endswith('upon restart') for status in statuses):
            self._plz_restart_label.config(text="Please restart Porcupine to apply the changes.")
        else:
            self._plz_restart_label.config(text="")

    def _on_select(self, junk: object = None) -> None:
        [plugin_name] = self._treeview.selection()
        [info] = [info for info in pluginloader.plugin_infos if info.name == plugin_name]

        if info.status == pluginloader.Status.IMPORT_FAILED:
            text = f"Importing the plugin failed.\n\n{info.error}"
        elif info.status == pluginloader.Status.SETUP_FAILED:
            text = f"The plugin's setup() function failed.\n\n{info.error}"
        elif info.status == pluginloader.Status.CIRCULAR_DEPENDENCY_ERROR:
            assert info.error is not None
            text = info.error
        else:
            text = get_docstring(f'porcupine.plugins.{info.name}')
            # get rid of single newlines
            text = re.sub(r'(.)\n(.)', r'\1 \2', text)

        self._title_label.config(text=plugin_name)
        self._description.config(state='normal')
        self._description.delete('1.0', 'end')
        self._description.insert('1.0', text)
        self._description.config(state='disabled')

        disable_list = settings.get('disabled_plugins', List[str])
        self._enable_disable_button.config(
            state='normal', text=("Enable" if plugin_name in disable_list else "Disable"))

    def _toggle_enabled(self) -> None:
        [plugin_name] = self._treeview.selection()
        [info] = [info for info in pluginloader.plugin_infos if info.name == plugin_name]

        disabled = set(settings.get('disabled_plugins', List[str]))
        disabled ^= {plugin_name}
        settings.set('disabled_plugins', list(disabled))

        if plugin_name not in disabled and pluginloader.can_setup_while_running(info):
            pluginloader.setup_while_running(info)

        self._update_row(info)
        self._on_select()
        self._update_plz_restart_label()


def show_dialog() -> None:
    dialog = tkinter.Toplevel()
    PluginDialogContent(dialog).content.pack(fill='both', expand=True)
    dialog.transient(get_main_window())
    dialog.geometry(f'{DIALOG_WIDTH}x{DIALOG_HEIGHT}')
    dialog.minsize(DIALOG_WIDTH, DIALOG_HEIGHT)
    dialog.wait_window()


def setup() -> None:
    menubar.get_menu("Settings").add_command(label="Plugin Manager", command=show_dialog)
