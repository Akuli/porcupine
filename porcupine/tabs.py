r"""Tabs as in browser tabs, not \t characters.

Yes, I am aware of ``ttk.Notebook`` but it's simply way too limited for
Porcupine. I can't even add a closing button or change the color of the
top label.
"""

import functools
import hashlib
import logging
import os
import tkinter as tk
from tkinter import messagebox
import traceback

from porcupine import dialogs, find, textwidget, utils
from porcupine.settings import config

log = logging.getLogger(__name__)


class TabManager(tk.Frame):
    """A simple but awesome tab widget.

    The tabs attribute is meant to be read-only. The results of
    modifying it are undefined.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # no, this is not a find/replace error, topframeframe is a frame
        # that contains topframes
        self._topframeframe = tk.Frame(self)
        self._topframeframe.pack(fill='x')
        utils.bind_mouse_wheel(self._topframeframe, self._on_wheel)
        self.tabs = []
        self.new_tab_hook = utils.ContextManagerHook(__name__)
        self.tab_changed_hook = utils.CallbackHook(__name__)
        self._current_tab = None
        self.no_tabs_frame = tk.Frame(self)
        self.no_tabs_frame.pack(fill='both', expand=True)

        # These can be bound in a parent widget. Note that the callbacks
        # should be called with no arguments.
        self.bindings = [
            ('<Control-Prior>', functools.partial(self.select_left, True)),
            ('<Control-Next>', functools.partial(self.select_right, True)),
            ('<Control-Shift-Prior>', self.move_left),
            ('<Control-Shift-Next>', self.move_right),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number-1)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

    @property
    def current_tab(self):
        return self._current_tab

    @current_tab.setter
    def current_tab(self, tab):
        assert tab is None or tab in self.tabs  # TODO: validate better
        if tab is self._current_tab:
            return

        # there's always a tab or no tabs message, let's hide it
        if self.current_tab is None:
            self.no_tabs_frame.pack_forget()
        else:
            self.current_tab._topframe['relief'] = 'raised'
            self.current_tab.content.pack_forget()

        # and then replace it with the new tab or no tabs message
        if tab is None:
            self.no_tabs_frame.pack(fill='both', expand=True)
        else:
            tab._topframe['relief'] = 'sunken'
            tab.content.pack(fill='both', expand=True)
            tab.on_focus()

        self._current_tab = tab
        self.tab_changed_hook.run(tab)

    @property
    def current_index(self):
        if self.current_tab is None:
            return None
        return self.tabs.index(self.current_tab)

    @current_index.setter
    def current_index(self, index):
        if index < 0:
            # this would create weird rollovers so maybe best to avoid
            raise IndexError
        self.current_tab = self.tabs[index]

    def add_tab(self, tab, make_current=True):
        """Add a :class:`Tab` to this tab manager.

        If *make_current* is True, :attr:`current_tab` will be set to
        *tab*.
        """
        tab._topframe.grid(row=0, column=len(self.tabs))
        self.tabs.append(tab)
        if self.current_tab is None:
            # this is the first tab
            self.current_tab = tab

        tab.__hook_context_manager = self.new_tab_hook.run(tab)
        tab.__hook_context_manager.__enter__()
        if make_current:
            self.current_tab = tab
        return tab

    def _remove_tab(self, tab):
        if tab is self.current_tab:
            # go to next or previous tab if there are other tabs,
            # otherwise unselect the tab
            if not (self.select_right() or self.select_left()):
                self.current_tab = None

        tab.__hook_context_manager.__exit__(None, None, None)
        tab.content.pack_forget()
        tab._topframe.grid_forget()

        # the grid columns of topframes of tabs after this change, so we
        # need to take care of that
        where = self.tabs.index(tab)
        del self.tabs[where]
        for i in range(where, len(self.tabs)):
            self.tabs[i]._topframe.grid(column=i)

    def _select_next_to(self, diff, roll_over):
        if len(self.tabs) < 2:
            return False

        if roll_over:
            self.current_index = (self.current_index + diff) % len(self.tabs)
            return True
        try:
            self.current_index += diff
            return True
        except IndexError:
            return False

    def select_left(self, roll_over=False):
        """Switch to the tab at left if possible.

        If roll_over is True and the current tab is the first tab in
        this widget, switch to the last tab. Return True if the current
        tab was changed.
        """
        return self._select_next_to(-1, roll_over)

    def select_right(self, roll_over=False):
        """Like select_left(), but switch to the tab at right."""
        return self._select_next_to(+1, roll_over)

    def _on_wheel(self, direction):
        diffs = {'up': -1, 'down': +1}
        self._select_next_to(diffs[direction], False)

    def _swap(self, i1, i2):
        self.tabs[i1], self.tabs[i2] = self.tabs[i2], self.tabs[i1]
        for i in (i1, i2):
            # tk allows gridding multiple widgets in the same place, and
            # gridding an already gridded widget moves it
            self.tabs[i]._topframe.grid(column=i)

    def move_left(self):
        """Move the current tab left if possible.

        Return True if the tab was moved.
        """
        if self.current_index in {None, 0}:
            return False
        self._swap(self.current_index, self.current_index-1)
        return True

    def move_right(self):
        """Like move_left(), but moves right."""
        if self.current_index in {None, len(self.tabs)-1}:
            return False
        self._swap(self.current_index, self.current_index+1)
        return True

    def _on_alt_n(self, index):
        try:
            self.current_index = index
            return 'break'
        except IndexError:
            return None


class Tab:
    """A tab that can be added to TabManager."""

    def __init__(self, manager):
        self.manager = manager

        def select_me(event):
            manager.current_tab = self

        self._topframe = tk.Frame(manager._topframeframe, relief='raised',
                                  border=1, padx=10, pady=3)
        self._topframe.bind('<Button-1>', select_me)

        self.label = tk.Label(self._topframe)
        self.label.pack(side='left')
        self.label.bind('<Button-1>', select_me)

        # Subclasses can add stuff here.
        self.content = tk.Frame(manager)

        def _close_if_can(event):
            if self.can_be_closed():
                self.close()

        closebutton = tk.Label(
            self._topframe, image=utils.get_image('closebutton.gif'))
        closebutton.pack(side='left')
        closebutton.bind('<Button-1>', _close_if_can)

        utils.bind_mouse_wheel(self._topframe, manager._on_wheel)
        utils.bind_mouse_wheel(self.label, manager._on_wheel)
        utils.bind_mouse_wheel(closebutton, manager._on_wheel)

    def can_be_closed(self):
        """Check if this tab can be closed.

        This always returns True by default. You can override this in a
        subclass.
        """
        return True

    def close(self):
        """Remove this tab from the tab manager.

        Overrides must call super().
        """
        self.manager._remove_tab(self)
        self._topframe.destroy()
        self.content.destroy()

    def on_focus(self):
        """This is called when the tab is selected.

        This does nothing by default. You can override this in a
        subclass and make this focus the main widget if the tab has one.
        """


class FileTab(Tab):
    """A tab that represents an opened file."""

    def __init__(self, manager):
        super().__init__(manager)
        self.label['text'] = "New File"
        self._path = None
        self.path_changed_hook = utils.CallbackHook(__name__)

        self._orig_label_fg = self.label['fg']
        self.path_changed_hook.connect(self._update_top_label)

        self.mainframe = tk.Frame(self.content)
        self.mainframe.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self.mainframe, width=1, height=1, wrap='none')
        self.textwidget.modified_hook.connect(self._update_top_label)
        self.scrollbar = tk.Scrollbar(self.mainframe)

        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

        # these are packed right-to-left because the linenumbers are at
        # left and can be pack_forgot()ten
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget.pack(side='right', fill='both', expand=True)

        self._findwidget = None

        self.mark_saved()
        self._update_top_label()

    def _get_hash(self):
        result = hashlib.md5()
        encoding = config['Files', 'encoding']   # superstitious speed-up
        for chunk in self.textwidget.iter_chunks():
            chunk = chunk.encode(encoding, errors='replace')
            result.update(chunk)
        return result.hexdigest()

    def mark_saved(self):
        """Make the tab look like it's saved."""
        self._save_hash = self._get_hash()
        self._update_top_label()

    def is_saved(self):
        """Return False if the text has changed since previous save.

        Use mark_saved() to set this.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self):
        """The file path where this file is currently saved.

        This is None if the file has never been saved.
        """
        return self._path

    @path.setter
    def path(self, new_path):
        # FIXME: use os.path.samefile() or something else that takes in
        # account things like case-insensitive paths?
        it_changes = (self._path != new_path)
        self._path = new_path
        if it_changes:
            self.path_changed_hook.run(new_path)

    def _update_top_label(self, junk=None):
        if self.path is not None:
            self.label['text'] = os.path.basename(self.path)

        if self.is_saved():
            self.label['fg'] = self._orig_label_fg
        else:
            self.label['fg'] = 'red'

    def can_be_closed(self):
        """If needed, display a "wanna save?" dialog and save.

        Return False if the user cancels and True otherwise. This
        overrides :meth:`.Tab.can_be_closed`.
        """
        if not self.is_saved():
            if self.path is None:
                msg = "Do you want to save your changes?"
            else:
                msg = ("Do you want to save your changes to %s?"
                       % self.path)
            answer = messagebox.askyesnocancel("Close file", msg)
            if answer is None:
                # cancel
                return False
            if answer:
                # yes
                self.save()
        return True

    def close(self):
        super().close()
        self.textwidget.modified_hook.disconnect(self._update_top_label)

    def on_focus(self):
        self.textwidget.focus()

    @classmethod
    def from_file_object(cls, manager, file):
        """Read a file object and create new FileTab from that.

        The :attr:`path` attribute is set to None.

        .. seealso:: The :meth:`from_path` method.
        """
        tab = cls(manager)
        tab.mark_saved()
        for chunk in utils.read_chunks(file):
            tab.textwidget.insert('end - 1 char', chunk)
        if hasattr(file, 'name'):
            tab.label['text'] = file.name
        tab.textwidget.edit_reset()     # reset undo/redo
        return tab

    @classmethod
    def from_path(cls, manager, path=None, *, content=None):
        """Open a file from a path.

        The *manager* should be a :class:`.TabManager`. The content will
        be read from the path if *content* is not given.

        If the file is already opened, this sets ``manager.current_tab``
        to the file's tab and returns the tab. Otherwise the new FileTab
        object is returned.
        """
        # maybe this file is open already?
        for tab in manager.tabs:
            # we don't use == because paths are case-insensitive on
            # windows
            if (isinstance(path, cls) and tab.path is not None
                    and os.path.samefile(path, tab.path)):
                manager.current_tab = tab
                return tab

        tab = cls(manager)
        tab.path = path

        if content is None:
            encoding = config['Files', 'encoding']
            with open(path, 'r', encoding=encoding) as file:
                for chunk in utils.read_chunks(file):
                    tab.textwidget.insert('end - 1 char', chunk)
        else:
            tab.textwidget.insert('1.0', content)

        tab.textwidget.edit_reset()   # reset undo/redo
        tab.mark_saved()
        return tab

    def save(self):
        """Save the file.

        This calls :meth:`save_as` if :attr:`path` is None.
        """
        if self.path is None:
            self.save_as()
            return

        if self.textwidget.get('end - 2 chars', 'end - 1 char') != '\n':
            # doesn't end with a \n yet
            # TODO: turn this into a plugin
            if config['Files', 'add_trailing_newline']:
                # make sure we don't move the cursor, IDLE does it and
                # it's annoying
                here = self.textwidget.index('insert')
                self.textwidget.insert('end - 1 char', '\n')
                self.textwidget.mark_set('insert', here)

        try:
            encoding = config['Files', 'encoding']
            with utils.backup_open(self.path, 'w', encoding=encoding) as f:
                for chunk in self.textwidget.iter_chunks():
                    f.write(chunk)
        except (OSError, UnicodeError) as e:
            log.exception("saving '%s' failed", self.path)
            utils.errordialog(type(e).__name__, "Saving failed!",
                              traceback.format_exc())
            return

        self.mark_saved()

    def save_as(self):
        """Ask the user where to save the file and save it there."""
        path = dialogs.save_as(old_path=self.path)
        if path is not None:
            self.path = path
            self.save()

    # TODO: turn this into a plugin!
    def find(self):
        if self._findwidget is None:
            log.debug("find widget not created yet, creating it")
            self._findwidget = find.Finder(self.content, self.textwidget)
        self._findwidget.pack(fill='x')


if __name__ == '__main__':
    # test/demo
    root = tk.Tk()
    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.tab_changed_hook.connect(print)

    tk.Label(tabmgr.no_tabs_frame, text="u have no open tabs :(").pack()

    for keysym, callback in tabmgr.bindings:
        root.bind(keysym, (lambda event, c=callback: c()))

    for i in range(1, 6):
        tab = Tab(tabmgr)
        tab.label['text'] = "tab %d" % i
        text = tk.Text(tab.content)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)
        tabmgr.add_tab(tab)

    root.mainloop()
