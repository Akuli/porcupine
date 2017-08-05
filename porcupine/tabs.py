r"""Tabs as in browser tabs, not \t characters."""

# Yes, I am aware of ``ttk.Notebook`` but it's way too limited for
# Porcupine. I can't even add a closing button or change the color of
# the top label.

import functools
import hashlib
import logging
import os
import tkinter as tk
from tkinter import messagebox
import traceback

import porcupine
from porcupine import dialogs, filetypes, _find, textwidget, utils
from porcupine.settings import config

log = logging.getLogger(__name__)


class TabManager(tk.Frame):
    """A simple but awesome tab widget.

    The tabs attribute is meant to be read-only. The results of
    modifying it are undefined.

    Virtual events:

    ``<<NewTab>>``
        This runs after a new tab has been added to this tab manager
        with :meth:`~add_tab`. The tab is always added to the end of
        :attr:`~tabs`, so you can access it with
        ``event.widget.tabs[-1]``.

        Bind to the ``<Destroy>`` event of the tab if you want to clean
        up something when the tab is closed.

    ``<<CurrentTabChanged>>``
        This runs when the user selects another tab or Porcupine does it
        for some reason. Use ``event.widget.current_tab`` to get or set
        the currently selected tab.

        .. seealso:: :attr:`~current_tab`
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # no, this is not a find/replace error, topframeframe is a frame
        # that contains topframes
        self._topframeframe = tk.Frame(self)
        self._topframeframe.pack(fill='x')
        utils.bind_mouse_wheel(self._topframeframe, self._on_wheel)

        #: List of :class:`.Tab` objects. This is supposed to be
        #: read-only, don't modify this.
        self.tabs = []

        self._current_tab = None
        self.no_tabs_frame = tk.Frame(self)
        self.no_tabs_frame.pack(fill='both', expand=True)

        def on_page_updown(shifted, event):
            if shifted:
                if event.keysym == 'Prior':
                    self.move_left()
                else:
                    self.move_right()
            else:
                if event.keysym == 'Prior':
                    self.select_left(True)
                else:
                    self.select_right(True)

            return 'break'

        # These can be bound in a parent widget.
        self.bindings = [
            ('<Control-Prior>', functools.partial(on_page_updown, False)),
            ('<Control-Next>', functools.partial(on_page_updown, False)),
            ('<Control-Shift-Prior>', functools.partial(on_page_updown, True)),
            ('<Control-Shift-Next>', functools.partial(on_page_updown, True)),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

    @property
    def current_tab(self):
        """The tab that the user has currently selected.

        This is None when there are no tabs. Don't set this if there are
        no tabs.
        """
        return self._current_tab

    @current_tab.setter
    def current_tab(self, tab):
        assert tab is None or tab in self.tabs
        if tab is self._current_tab:
            return

        # there's always a tab or no tabs message, let's hide it
        if self.current_tab is None:
            self.no_tabs_frame.pack_forget()
        else:
            self.current_tab._topframe['relief'] = 'raised'
            self.current_tab.pack_forget()

        # and then replace it with the new tab or no tabs message
        if tab is None:
            self.no_tabs_frame.pack(fill='both', expand=True)
        else:
            tab._topframe['relief'] = 'sunken'
            tab.pack(fill='both', expand=True)
            tab.on_focus()

        self._current_tab = tab
        self.event_generate('<<CurrentTabChanged>>')

    @property
    def current_index(self):
        """The index of :attr:`current_tab` in :attr:`.tabs`.

        Setting this raises :exc:`IndexError` if the index is too big or
        too small. Negative indexes are not supported.
        """
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
        """Append a :class:`Tab` to this tab manager.

        If ``tab.equivalent(existing_tab)`` returns True for any
        ``existing_tab`` that is already in the tab manager, then that
        existing tab is returned. Otherwise *tab* is added to the tab
        manager and returned.

        If *make_current* is True, then :attr:`current_tab` is set to
        the tab that is returned.

        .. seealso:: :meth:`.Tab.equivalent` and :meth:`.Tab.close`.
        """
        assert tab not in self.tabs, "cannot add the same tab twice"
        for existing_tab in self.tabs:
            if tab.equivalent(existing_tab):
                if make_current:
                    self.current_tab = existing_tab
                return existing_tab

        tab._topframe.grid(row=0, column=len(self.tabs))
        self.tabs.append(tab)
        if self.current_tab is None or make_current:
            # this is the first tab or it's supposed to become the
            # current tab for some other reason
            self.current_tab = tab

        self.event_generate('<<NewTab>>')
        return tab

    # this is called only from Tab.close()
    def _remove_tab(self, tab):
        if tab is self.current_tab:
            # go to next or previous tab if there are other tabs,
            # otherwise unselect the tab
            if not (self.select_right() or self.select_left()):
                self.current_tab = None

        tab.pack_forget()
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

        If *roll_over* is True and the current tab is the first tab in
        this widget, switch to the last tab. Return True if the current
        tab was changed.
        """
        return self._select_next_to(-1, roll_over)

    def select_right(self, roll_over=False):
        """Like :meth:`select_left`, but switch to the tab at right."""
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
        self._swap(self.current_index, self.current_index-1)    # noqa
        return True

    def move_right(self):
        """Like :meth:`move_left`, but moves right."""
        if self.current_index in {None, len(self.tabs)-1}:   # noqa
            return False
        self._swap(self.current_index, self.current_index+1)    # noqa
        return True

    def _on_alt_n(self, n, event):
        try:
            self.current_index = n - 1
            return 'break'
        except IndexError:
            pass

    def destroy(self):
        """Close all tabs and destroy all remaining child widgets.

        Tkinter calls this automatically when the tab manager's parent
        widget is destroyed.
        """
        # need to loop over a copy because closing a tab also removes it
        # from self.tabs
        for tab in self.tabs.copy():
            tab.close()
        super().destroy()


class Tab(tk.Frame):
    """A tab widget that can be added to :class:`TabManager`.

    Use ``tab.master`` to get the tab manager of a tab.
    """

    def __init__(self, manager):
        super().__init__(manager)

        def select_me(event):
            manager.current_tab = self

        self._topframe = tk.Frame(manager._topframeframe, relief='raised',
                                  border=1, padx=10, pady=3)
        self._topframe.bind('<Button-1>', select_me)

        # TODO: rename this to top_label
        self.label = tk.Label(self._topframe)
        self.label.pack(side='left')
        self.label.bind('<Button-1>', select_me)

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

    # TODO: replace this with a TabManager.close_tab() method and
    # binding <Destroy>
    def close(self):
        """Remove this tab from the tab manager.

        Call ``super().close()`` if you override this in a subclass.
        """
        self.master._remove_tab(self)
        self._topframe.destroy()
        self.destroy()

    def on_focus(self):
        """This is called when the tab is selected.

        This does nothing by default. You can override this in a
        subclass and make this focus the tab's main widget if needed.
        """

    def equivalent(self, other):
        """This is explained in :meth:`.TabManager.add_tab`.

        This always returns False by default, but you can override it in
        a subclass. For example::

            class MyCoolTab(tabs.Tab):
                ...

                def equivalent(self, other):
                    if isinstance(other, MyCoolTab):
                        # other can be used instead of this tab if its
                        # thingy is same as this tab's thingy
                        return (self.thingy == other.thingy)
                    else:
                        # MyCoolTabs are never equivalent to other kinds
                        # of tabs
                        return False
        """
        return False


class FileTab(Tab):
    """A tab that represents an opened file.

    The tab will have *content* in it by default when it's opened. If
    *path* is given, the file will be saved there when the user presses
    Ctrl+S; otherwise the user will be asked to choose a path.
    """

    def __init__(self, manager, content=None, *, path=None):
        super().__init__(manager)
        self.label['text'] = "New File"
        self._save_hash = None

        # path and filetype are set correctly below
        self._path = None
        self._filetype = filetypes.filetypes['Text only']
        self.path_changed_hook = utils.CallbackHook(__name__)
        self.filetype_changed_hook = utils.CallbackHook(__name__)

        # TODO: try to guess the filetype from the content when path is None
        self.path_changed_hook.connect(self._guess_filetype)

        self._orig_label_fg = self.label['fg']
        self.path_changed_hook.connect(self._update_top_label)

        # FIXME: wtf is this doing here?
        self.mainframe = tk.Frame(self)
        self.mainframe.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self.mainframe, self._filetype, width=1, height=1,
            wrap='none', undo=True)
        self.filetype_changed_hook.connect(self.textwidget.set_filetype)
        self.textwidget.bind('<<ContentChanged>>', self._update_top_label,
                             add=True)

        # everything seems to work ok without this except that e.g.
        # pressing Ctrl+O in the text widget opens a file AND inserts a
        # newline (Tk inserts a newline by default)
        utils.copy_bindings(porcupine.get_main_window(), self.textwidget)

        self.scrollbar = tk.Scrollbar(self.mainframe)
        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

        # these are packed right-to-left because the linenumbers are at
        # left and can be pack_forgot()ten
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget.pack(side='right', fill='both', expand=True)

        self._findwidget = None

        self.path = path
        if content is not None:
            self.textwidget.insert('1.0', content)
            self.textwidget.edit_reset()   # reset undo/redo

        self.mark_saved()
        self._update_top_label()

    def equivalent(self, other):
        """Return True if *self* and *other* are saved to the same place.

        This returns False if *other* is not a FileTab or the
        :attr:`path` attributes of both tabs are None.
        """
        # this used to have hasattr(other, "path") instead of isinstance
        # but it screws up if a plugin defines something different with
        # a path attribute, for example, a debugger plugin might have
        # tabs that represent files and they might need to be opened at
        # the same time as FileTabs are
        # note that this returns False when the paths of both tabs are
        # None, so it's possible to have multiple "New File" tabs
        return (isinstance(other, FileTab) and
                self.path is not None and
                other.path is not None and
                os.path.samefile(self.path, other.path))

    def _get_hash(self):
        result = hashlib.md5()
        encoding = config['Files', 'encoding']   # superstitious speed-up
        for chunk in self.textwidget.iter_chunks():
            chunk = chunk.encode(encoding, errors='replace')
            result.update(chunk)

        # hash objects don't define an __eq__ so we need to use a string
        # representation of the hash
        return result.hexdigest()

    def mark_saved(self):
        """Make the tab look like it's saved.

        This makes :meth:`is_saved` return True.
        """
        self._save_hash = self._get_hash()
        self._update_top_label()

    def is_saved(self):
        """Return False if the text has changed since previous save.

        Use :meth:`mark_saved` to set this.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self):
        """Path to where this file is currently saved.

        This is None if the file has never been saved.
        """
        return self._path

    @path.setter
    def path(self, new_path):
        if self.path is None and new_path is None:
            it_changes = False
        elif self.path is None or new_path is None:
            it_changes = True
        else:
            # windows paths are case-insensitive
            it_changes = (os.path.normcase(self._path) !=
                          os.path.normcase(new_path))

        self._path = new_path
        if it_changes:
            self.path_changed_hook.run(new_path)

    @property
    def filetype(self):
        """A value from :data:`porcupine.filetypes.filetypes`."""
        return self._filetype

    @filetype.setter
    def filetype(self, filetype):
        assert filetype in filetypes.filetypes.values()
        self._filetype = filetype
        self.filetype_changed_hook.run(filetype)

    def _guess_filetype(self, new_path):
        print("guessing filetype from", new_path)
        if new_path is None:
            # there's no way to "unsave a file", but a plugin might do
            # that for whatever reason
            self.filetype = filetypes.filetypes['Text only']
        else:
            self.filetype = filetypes.guess_filetype(new_path)

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
        if self.is_saved():
            return True

        if self.path is None:
            msg = "Do you want to save your changes?"
        else:
            msg = ("Do you want to save your changes to %s?"
                   % os.path.basename(self.path))
        answer = messagebox.askyesnocancel("Close file", msg)
        if answer is None:
            # cancel
            return False
        if answer:
            # yes
            return self.save()
        # no was clicked, can be closed
        return True

    def on_focus(self):
        self.textwidget.focus()

    def save(self):
        """Save the file.

        This calls :meth:`save_as` if :attr:`path` is None, and returns
        False if the user cancels the save as dialog. None is returned
        on errors, and True is returned in all other cases.
        """
        if self.path is None:
            return self.save_as()

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
            return None

        self.mark_saved()
        return True

    def save_as(self):
        """Ask the user where to save the file and save it there.

        Returns True if the file was saved, and False if the user
        cancelled the dialog.
        """
        path = dialogs.save_as(old_path=self.path)
        if path is None:
            return False
        self.path = path
        self.save()
        return True

    # TODO: turn this into a plugin!
    def find(self):
        """This method will probably be removed soon. Don't use it."""
        if self._findwidget is None:
            log.debug("find widget not created yet, creating it")
            self._findwidget = _find.Finder(self, self.textwidget)
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
        text = tk.Text(tab)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)
        tabmgr.add_tab(tab)

    root.mainloop()
