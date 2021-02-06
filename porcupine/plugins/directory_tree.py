import pathlib
import tkinter
import tkinter.ttk as ttk

from porcupine import get_paned_window, get_tab_manager, tabs


# TODO: handle files being deleted, copied, renamed, etc
# TODO: scroll bar
class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse')
        self.paths = {'': pathlib.Path('.').resolve()}
        self.process_directory('')
        self.bind('<<TreeviewSelect>>', self.on_click, add=True)
        self.tag_configure('dummy', foreground='gray')   # TODO: use ttk theme?

    def process_directory(self, parent: str) -> None:
        for child in self.get_children(parent):
            if 'dummy' not in self.item(child, 'tags'):
                del self.paths[child]
            self.delete(child)

        paths = sorted(self.paths[parent].iterdir())
        if paths:
            for path in paths:
                n = self.insert(parent, 'end', text=path.name, open=False)
                self.paths[n] = path
                if path.is_dir():
                    self._insert_dummy(n)
        else:
            self._insert_dummy(parent)

    def on_click(self, event: tkinter.Event) -> None:
        [selection] = self.selection()
        if 'dummy' not in self.item(selection, 'tags'):
            path = self.paths[selection]
            if path.is_dir():
                self.process_directory(selection)
            else:
                get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))

    def _insert_dummy(self, parent: str) -> None:
        self.insert(parent, 'end', text='(empty)', tags='dummy')


def setup() -> None:
    sidebar = DirectoryTree(get_paned_window())
    get_paned_window().insert(get_tab_manager(), sidebar)   # put sidebar before tab manager
