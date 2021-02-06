import pathlib
import tkinter
import tkinter.ttk as ttk

from porcupine import get_paned_window, get_tab_manager, tabs


# TODO: handle files being deleted, copied, renamed, etc
class DirectoryTree(ttk.Treeview):

    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, selectmode='browse')
        self.process_directory(pathlib.Path('.').resolve(), '')
        self.bind('<<TreeviewSelect>>', self.on_click, add=True)
        self.tag_configure('dummy', foreground='gray')   # TODO: use ttk theme?

    def process_directory(self, dir_path: pathlib.Path, parent_id: str) -> None:
        for child in self.get_children(parent_id):
            self.delete(child)

        paths = sorted(dir_path.iterdir())
        if paths:
            for path in paths:
                n = self.insert(parent_id, 'end', text=path.name, values=[path], open=False)
                if path.is_dir():
                    self._insert_dummy(n)
        else:
            self._insert_dummy(parent_id)

    def on_click(self, event: tkinter.Event) -> None:
        [selection] = self.selection()
        if 'dummy' not in self.item(selection, 'tags'):
            path = pathlib.Path(self.item(selection, 'values')[0])
            if path.is_dir():
                self.process_directory(path, selection)
            else:
                get_tab_manager().add_tab(tabs.FileTab.open_file(get_tab_manager(), path))

    def _insert_dummy(self, parent: str) -> None:
        self.insert(parent, 'end', text='(empty)', tags='dummy')


def setup() -> None:
    container = ttk.Frame(get_paned_window())
    tree = DirectoryTree(container)
    tree.pack(side='left', fill='both', expand=True)
    scrollbar = ttk.Scrollbar(container)
    scrollbar.pack(side='right', fill='y')

    tree.config(yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    get_paned_window().insert(get_tab_manager(), container)   # insert before tab manager
