"""Open a file in Porcupine when it's dragged and dropped from file manager."""
import pathlib
import tkinter
import logging

from porcupine import get_main_window, get_tab_manager, tabs

log = logging.getLogger(__name__)


def handle_drop(paths_from_tcl: str) -> None:
    for path in map(pathlib.Path, get_main_window().tk.splitlist(paths_from_tcl)):
        if path.is_file():
            get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))
        else:
            log.warning(f"can't open '{path}' because it is not a file")


def setup() -> None:
    root = get_main_window()
    try:
        root.tk.eval('package require tkdnd')
    except tkinter.TclError:
        log.warning("Drag and drop will not work because tkdnd is not installed")
        log.debug("tkdnd loading failure:", exc_info=True)
        return

    root.tk.eval('''
    # https://github.com/petasis/tkdnd/blob/master/demos/simple_target.tcl
    tkdnd::drop_target register . DND_Files

    # can't bind in tkinter, because tkinter's bind doesn't understand tkdnd events:
    # _tkinter.TclError: expected integer but got "%#"
    bind . <<Drop:DND_Files>> {''' + root.register(handle_drop) + ''' %D}
    ''')
