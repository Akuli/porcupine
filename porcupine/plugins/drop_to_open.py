"""Open a file in Porcupine when it's dragged and dropped from file manager."""
import logging
import pathlib
import tkinter

from porcupine import get_main_window, get_tab_manager

log = logging.getLogger(__name__)


def handle_drop(paths_from_tcl: str) -> None:
    for path in map(pathlib.Path, get_main_window().tk.splitlist(paths_from_tcl)):
        if path.is_file():
            tab = get_tab_manager().open_file(path)
            if tab is not None:
                get_tab_manager().add_tab(tab)
        else:
            log.warning(f"can't open '{path}' because it is not a file")


def setup() -> None:
    root = get_main_window()
    try:
        root.tk.eval("package require tkdnd")
    except tkinter.TclError:
        log.error("dragging files to Porcupine won't work because tkdnd isn't installed")
        log.debug("full error:", exc_info=True)
    else:
        root.tk.eval(
            """
            # https://github.com/petasis/tkdnd/blob/master/demos/simple_target.tcl
            tkdnd::drop_target register . DND_Files

            # can't bind in tkinter, because tkinter's bind doesn't understand tkdnd events:
            # _tkinter.TclError: expected integer but got "%#"
            bind . <<Drop:DND_Files>> {DROPCOMMAND %D}
            """.replace(
                "DROPCOMMAND", root.register(handle_drop)
            )
        )
