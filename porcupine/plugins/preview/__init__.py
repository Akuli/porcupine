from __future__ import annotations

from porcupine import get_tab_manager, settings, tabs

from .widget import MarkupPreview


def on_new_filetab(tab: tabs.FileTab) -> None:
    if not tab.path:
        return

    if "filetype_name" in tab.settings._options:
        file_type = tab.settings.get("filetype_name")
    elif "filetype_name" in tab.settings.get_state():
        file_type = tab.settings.get_state()["filetype_name"].value
    else:
        return

    if file_type != "Markdown":
        # FIXME: filetype can change
        return

    preview = MarkupPreview(tab.panedwindow, editor=tab.textwidget, path=tab.path)
    tab.panedwindow.add(preview, stretch="never")
    settings.remember_pane_size(tab.panedwindow, preview, "preview_width", 350)


def setup():
    get_tab_manager().add_filetab_callback(on_new_filetab)
