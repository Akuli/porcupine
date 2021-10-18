"""
Open the current file in a webbrowser.

Available in Tools/Web/Open in webbrowser.
"""

from __future__ import annotations

import logging
import webbrowser

from porcupine import menubar, tabs

log = logging.getLogger(__name__)


def open_file_in_browser(tab: tabs.FileTab) -> None:
    try:
        webbrowser.open(str(tab.path))
    except webbrowser.Error:
        log.warning(f"Can't open {str(tab.path)} in webbrowser")
    else:
        log.info(f"Succesfully opened {str(tab.path)} in webbrowser")


def setup() -> None:
    menubar.add_filetab_command("Tools/Web/Open in webbrowser", open_file_in_browser)
