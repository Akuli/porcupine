"""A convenient way to view Porcupine logs of the running Porcupine instance."""

from __future__ import annotations
import tkinter
from tkinter import ttk
from porcupine import menubar, _logs


class _LogViewer:

    def __init__(self) -> None:
        self.window = tkinter.Toplevel()
        self.window.withdraw()
        self.window.protocol('WM_DELETE_WINDOW', self.window.withdraw)
        self.window.title

        content_frame = ttk.Frame(self.window)
        content_frame.pack(fill="both", expand=True)
        self.last_size = 0

        self.textwidget = tkinter.Text(self.content_frame)
        self.textwidget.pack()
        scrollbar = ttk.Scrollbar(self.textwidget)

    def _refresh(self) -> None:
        _logs.current_log_path.stat().st_size

    def show(self) -> None:
        self.window.deiconify()
        self._refresh()


_viewer: _LogViewer | None = None


# for other plugins
def show(search_entry_text: str | None) -> None:
    if search_entry_text is not None:
        _viewer.search_entry.delete(0, 'end')
        _viewer.search_entry.insert(0, search_entry_text)
    _viewer.show()


def setup() -> None:
    global _viewer
    _viewer = _LogViewer()
    menubar.get_menu("Settings").add_command(label="Log viewer", command=view_logs)


