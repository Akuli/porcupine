r"""Tabs as in browser tabs, not \t characters."""
# TODO: user more callback objects and less virtual events?

import functools
import hashlib
import logging
import os
import traceback

import teek as tk

from porcupine import filetypes, images, settings, textwidget, utils

log = logging.getLogger(__name__)


class TabManager(tk.Notebook):
    """A simple but awesome tab widget.

    This widget inherits from :class:`pythotk.Notebook`. All tabs added to this
    should be :class:`Tab` objects.

    .. warning::
        Don't do something to a tab after adding it to a tab manager. This code
        is **BAD**::

            tab_manager.append(new_tab)
            new_tab.something.something()     # what if new_tab was closed?

        See :meth:`.Tab.equivalent` documentation for an explanation.

    .. attribute:: on_new_tab

        A :class:`pythotk.Callback` that runs with a new tab as an argument
        when a new tab has been added to the tab manager.

        Bind to the ``<Destroy>`` event of the tab if you want to clean
        up something when the tab is closed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.on_new_tab = tk.Callback()

        # These can be bound in a parent widget without event=True. This
        # doesn't use enable_traversal() because we want more bindings than it
        # creates.
        # TODO: document self.bindings?
        partial = functools.partial     # pep-8 line length
        self.bindings = [
            ('<Control-Prior>', partial(self._on_page_updown, False, -1)),
            ('<Control-Next>', partial(self._on_page_updown, False, +1)),
            ('<Control-Shift-Prior>', partial(self._on_page_updown, True, -1)),
            ('<Control-Shift-Next>', partial(self._on_page_updown, True, +1)),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

        self.bind('<<NotebookTabChanged>>', self._on_tab_changed)
        self.bind('<Button-1>', self._on_click, event=True)
        utils.bind_mouse_wheel(self, self._on_wheel)

    def _on_tab_changed(self):
        if self.selected_tab is not None:
            self.selected_tab.on_focus()

    def _on_click(self, event):
        # TODO: add identify to pythotk
        def identify(x, y):
            return tk.tcl_call(str, self, 'identify', x, y)

        if identify(event.x, event.y) != 'label':
            # something else than the top label was clicked
            return

        # TODO: add looking up a tab by coordinates to pythotk
        def coords2tab(x, y):
            index = tk.tcl_call(int, self, 'index', '@%d,%d' % (x, y))
            return None if index is None else self[index]

        # find the right edge of the label
        right = event.x
        while identify(right, event.y) == 'label':
            right += 1

        # hopefully the image is on the right edge of the label and
        # there's no padding :O
        if event.x + images.get('closebutton').width >= right:
            # the close button was clicked
            tab = coords2tab(event.x, event.y)
            if tab.can_be_closed():
                tab.close()

    def _on_wheel(self, direction):
        self.select_another_tab({'up': -1, 'down': +1}[direction])

    def _on_page_updown(self, shifted, diff):
        if shifted:
            self.move_selected_tab(diff)
        else:
            self.select_another_tab(diff)

    def _on_alt_n(self, n, event):
        if n-1 in range(len(self)):
            self.selected_tab = self[n-1]
            return True

        return False

    def select_another_tab(self, diff):
        """Try to select another tab next to the currently selected tab.

        *diff* should be ``1`` for selecting a tab at right or ``-1``
        for left. This returns True if another tab was selected, and
        False if the current tab is already the leftmost or rightmost tab or
        there are no tabs.
        """
        assert diff in {1, -1}, repr(diff)

        if self.selected_tab is not None:
            index = self.index(self.selected_tab)
            if index + diff in range(len(self)):
                self.selected_tab = self[index + diff]
                return True

        return False

    # TODO: test this
    def move_selected_tab(self, diff):
        """Try to move the currently selected tab left or right.

        *diff* should be ``1`` for moving to right or ``-1`` for left.
        This returns True if the tab was moved and False if there was no
        room for moving it or there are no tabs.
        """
        assert diff in {1, -1}, repr(diff)

        if self.selected_tab is not None:
            index = self.index(self.selected_tab)
            if index + diff in range(len(self)):
                # yes, this works, and also preserves selected_tab
                self.insert(index, self[index + diff])
                return True

        return False

    # empty docstring prevents this from showing up to sphinx
    def insert(self, index, tab):
        """"""
        assert isinstance(tab, Tab)
        if tab in self:
            # move an existing tab instead of adding a new tab
            super().insert(index, tab)
            return

        for old_tab in self:
            # refactoring note: must be tab.equivalent(old_tab) and not
            # old_tab.equivalent(tab), explained in Tab.equivalent docs
            if tab.equivalent(old_tab):
                tab.close()
                self.__info_for_append_and_select = old_tab    # this is dumb
                return

        # now we know that the tab should be actually added
        super().insert(index, tab)
        self.on_new_tab.run(tab)

    def append_and_select(self, tab):
        """
        Like the :meth:`pythotk.append_and_select` method this overrides, but
        works correctly with :meth:`~.Tab.equivalent` stuff.
        """
        self.append(tab)
        if tab.closed:
            self.selected_tab = self.__info_for_append_and_select
        else:
            self.selected_tab = tab


class Tab(tk.NotebookTab):
    r"""Base class for tabs that can be added to TabManager.

    This class inherits from :class:`pythotk.NotebookTab`, but pythotk tabs
    that are not instances of this class cannot be added to a
    :class:`.TabManager`.

    You can easily create custom kinds of tabs by inheriting from this
    class. Here's a very minimal but complete example plugin::

        import teek as tk
        from porcupine import actions, get_tab_manager, tabs

        class HelloTab(tabs.Tab):
            def __init__(self, manager):
                super().__init__(manager, title="Hello")
                tk.Label(self.content, "Hello World!").pack()

        def new_hello_tab():
            manager = get_tab_manager()
            manager.append_and_select(HelloTab(manager))

        def setup():
            actions.add_command('Hello/New Hello Tab', new_hello_tab)

    All initialization keyword arguments are passed to
    :class:`pythotk.NotebookTab`.

    .. attribute:: closed

        True if the tab has been closed (see :meth:`.close`), False otherwise.

    .. attribute:: status

        A human-readable string for showing in e.g. a status bar.

        The status message can also contain multiple tab-separated
        things, e.g. ``"File 'thing.py'\tLine 12, column 34"``.

        This is ``''`` by default, but that can be changed like
        ``tab.status = something_new``.

        If you're writing something like a status bar, make sure to
        handle ``\t`` characters and use :attr:`on_status_changed`.

    .. attribute:: on_status_changed

        A :class:`pythotk.Callback` that runs with no arguments when
        :attr:`status` is set to a new value.

    .. attribute:: content

        A frame that represents the content of the tab. You can add anything
        you want into this, and you can use any geometry manager you want.

    .. attribute:: top_frame
    .. attribute:: bottom_frame
    .. attribute:: left_frame
    .. attribute:: right_frame

        These are frame widgets that are packed to each side of the
        :attr:`.content` frame. Plugins add different kinds of things to these,
        for example, :source:`the statusbar <porcupine/plugins/statusbar.py>`
        is a widget in ``bottom_frame``.

        These frames contain no widgets when Porcupine is running
        without plugins. Use pack when adding things here.
    """

    def __init__(self, manager, **kwargs):
        super().__init__(tk.Frame(manager), image=images.get('closebutton'),
                         compound='right', **kwargs)

        self._status = ''
        self._closed = False

        self.on_status_changed = tk.Callback()

        # top and bottom frames must be packed first because this way
        # they extend past other frames in the corners
        self.top_frame = tk.Frame(self.widget)
        self.bottom_frame = tk.Frame(self.widget)
        self.left_frame = tk.Frame(self.widget)
        self.right_frame = tk.Frame(self.widget)
        self.top_frame.pack(side='top', fill='x')
        self.bottom_frame.pack(side='bottom', fill='x')
        self.left_frame.pack(side='left', fill='y')
        self.right_frame.pack(side='right', fill='y')

        # https://wiki.tcl-lang.org/page/frame "Frame does not shrink to 1
        # height if last children is unpacked/ungridded"
        # this bug was hard to find, and it only happened when there was
        # only 1 plugin using a frame
        tk.Frame(self.top_frame).pack()
        tk.Frame(self.bottom_frame).pack()
        tk.Frame(self.left_frame).pack()
        tk.Frame(self.right_frame).pack()

        self.content = tk.Frame(self.widget)
        self.content.pack(fill='both', expand=True)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status):
        self._status = new_status
        self.on_status_changed.run()

    # makes this read-only, prevents rare but hard-to-debug bugs
    @property
    def closed(self):
        return self._closed

    def can_be_closed(self):
        """
        This is usually called before the tab is closed. The tab
        shouldn't be closed if this returns False.

        By default, this always returns True, but you can override this
        in a subclass to do something more interesting. See
        :meth:`.FileTab.can_be_closed` for an example.

        When this method has returned True and it's time to actually close the
        tab, the tab is removed from the tab manager and all of its widgets are
        destroyed. Use their ``<Destroy>`` events to run callbacks when this
        happens.
        """
        return True

    def close(self):
        """Removes the tab from the manager and destroys all the tab's widgets.

        No error is raised if the tab is not in the tab manager. If you are
        going to call this, consider also using :meth:`.can_be_closed`. If you
        are going to override this, consider using ``<Destroy>`` events of the
        tab's widgets instead.
        """
        manager = self.widget.parent
        if self in manager:
            manager.remove(self)
        self.widget.destroy()
        self._closed = True

    def on_focus(self):
        """This is called when the tab is selected.

        This does nothing by default. You can override this in a
        subclass and make this focus the tab's main widget if needed.
        """

    def equivalent(self, other):
        """
        This is a way to prevent having multiple tabs that do the same thing.

        For example, if you open a file, and then you try to open that same
        file again, porcupine doesn't display a new file tab; instead, it
        selects the file tab that was already there. In :class:`.FileTab`, this
        method is overrided so that it returns True if *other* is a FileTab
        that represents the same file, and False otherwise.

        If a new tab is being added to :class:`TabManager` but there's
        already an equivalent tab in the manager, :class:`TabManager` closes
        the new tab. The equivalence is checked like
        ``new_tab.equivalent(old_tab)``, not ``old_tab.equivalent(new_tab)``.
        This difference could be useful for implementing tabs that are
        equivalent with tabs of other types for whatever reason.
        """
        return False

    def get_state(self):
        """Override this method to support opening a similar tab after \
restarting Porcupine.

        When Porcupine is closed,
        :source:`the restart plugin <porcupine/plugins/restart.py>`
        calls :meth:`get_state` methods of all tabs, and after starting
        Porcupine again it calls :meth:`from_state` methods.

        The returned state can be any picklable object. If it's None,
        the tab will not be restored at all after restarting, and by
        default, :meth:`get_state` always returns None.
        """
        return None

    @classmethod
    def from_state(cls, manager, state):
        """Create a new tab from the return value of :meth:`get_state`.

        Be sure to override this if you override :meth:`get_state`.
        """
        raise NotImplementedError(
            "from_state() wasn't overrided but get_state() was overrided")


class FileTab(Tab):
    """A tab that represents an opened file.

    The tab will have *content* in it by default when it's opened. If
    *path* is given, the file will be saved there when Ctrl+S is
    pressed. Otherwise this becomes a "New File" tab.

    If you want to read a file and open a new tab from it, use
    :meth:`open_file`. It uses things like the user's encoding settings.

    .. attribute:: on_save

        A :class:`pythotk.Callback` that runs with no arguments before the file
        is saved with the :meth:`save` method.

    .. attribute:: textwidget

        The central text widget of the tab.

        Currently this is a :class:`porcupine.textwidget.MainText`, but
        this is guaranteed to always be a
        :class:`HandyText <porcupine.textwidget.HandyText>`.

    .. attribute:: scrollbar

        This is the ``ttk.Scrollbar`` widget next to :attr:`.textwidget`.

        Things like :source:`the line number plugin <porcupine/plugins/linenum\
bers.py>` use this attribute.

    .. attribute:: path

        The path where this file is currently saved.

        This is None if the file has never been saved, and otherwise
        an absolute path as a string.

    .. attribute:: on_path_changed

        A :class:`pythotk.Callback` that runs with no arguments when
        :attr:`path` is set to a new value.

    .. attribute:: filetype

        A filetype object from :mod:`porcupine.filetypes`.

    .. attribute:: on_filetype_changed

        A :class:`pythotk.Callback` that runs with no arguments when
        :attr:`filetype` is set to a new value.
    """

    def __init__(self, manager, content='', path=None):
        super().__init__(manager)

        self.on_path_changed = tk.Callback()
        self.on_filetype_changed = tk.Callback()
        self.on_save = tk.Callback()

        self._save_hash = None

        self._path = path
        self._guess_filetype()          # sets self._filetype

        self.on_path_changed.connect(self._update_title)
        self.on_path_changed.connect(self._guess_filetype_if_needed)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self.content, self._filetype, width=1, height=1, wrap='none',
            undo=True)
        self.textwidget.pack(side='left', fill='both', expand=True)
        self.on_filetype_changed.connect(
            lambda: self.textwidget.set_filetype(self.filetype))
        self.textwidget.bind('<<ContentChanged>>', self._update_title)

        if content:
            self.textwidget.insert(self.textwidget.start, content)

            # this resets undo and redo
            # TODO: add 'edit reset' to pythotk
            tk.tcl_call(None, self.textwidget, 'edit', 'reset')

        self.on_path_changed.connect(self._update_status)
        self.on_filetype_changed.connect(self._update_status)
        self.textwidget.bind('<<CursorMoved>>', self._update_status)

        self.scrollbar = tk.Scrollbar(self.content)
        self.scrollbar.pack(side='left', fill='y')
        self.textwidget.config['yscrollcommand'].connect(self.scrollbar.set)
        self.scrollbar.config['command'].connect(self.textwidget.yview)

        self.mark_saved()
        self._update_title()
        self._update_status()

    @classmethod
    def open_file(cls, manager, path):
        """Read a file and return a new FileTab object.

        Use this constructor if you want to open an existing file from a
        path and let the user edit it.

        :exc:`UnicodeError` or :exc:`OSError` is raised if reading the
        file fails.
        """
        config = settings.get_section('General')
        with open(path, 'r', encoding=config['encoding']) as file:
            content = file.read()
        return cls(manager, content, path)

    def equivalent(self, other):
        """Return True if *self* and *other* are saved to the same place.

        This method overrides :meth:`Tab.can_be_closed` and returns
        False if other is not a FileTab or the path of at least one of
        the tabs is None. If neither path is None, this returns True if
        the paths point to the same file. This way, it's possible to
        have multiple "New File" tabs.
        """
        # this used to have hasattr(other, "path") instead of isinstance
        # but it screws up if a plugin defines something different with
        # a path attribute, for example, a debugger plugin might have
        # tabs that represent files and they might need to be opened at
        # the same time as FileTabs are
        #
        # TODO: handle cases where the file has been deleted
        return (isinstance(other, FileTab) and
                self.path is not None and
                other.path is not None and
                os.path.samefile(self.path, other.path))

    def _get_hash(self):
        # superstitious omg-optimization
        config = settings.get_section('General')
        encoding = config['encoding']

        result = hashlib.md5()
        for chunk in self.textwidget.iter_chunks():
            chunk = chunk.encode(encoding, errors='replace')
            result.update(chunk)

        # hash objects don't define an __eq__ so we need to use a string
        # representation of the hash
        return result.hexdigest()

    def mark_saved(self):
        """Make :meth:`is_saved` return True."""
        self._save_hash = self._get_hash()
        self._update_title()     # TODO: add a virtual event for this if needed

    def is_saved(self):
        """Return False if the text has changed since previous save.

        This is set to False automagically when the content is modified.
        Use :meth:`mark_saved` to set this to True.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self):
        return self._path

    # TODO: assert that the tab is absolute or make it absolute?
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
            self.on_path_changed.run()

    @property
    def filetype(self):
        return self._filetype

    # weird things might happen if filetype is of the wrong type
    @filetype.setter
    def filetype(self, filetype):
        try:
            # it's easier to write code that don't recurse infinitely if
            # 'tab.filetype = tab.filetype' does nothing
            if filetype is self._filetype:
                return
        except AttributeError:
            # this happens when called from _guess_filetype, and self._filetype
            # hasn't been set yet
            pass

        self._filetype = filetype
        self.on_filetype_changed.run()

    def _guess_filetype(self):
        if self.path is None:
            name = settings.get_section('File Types')['default_filetype']
            self.filetype = filetypes.get_filetype_by_name(name)
        else:
            # FIXME: this may read the shebang from the file, but the file
            #        might not be saved yet because save_as() sets self.path
            #        before saving, and that's when this runs
            self.filetype = filetypes.guess_filetype(self.path)

    def _guess_filetype_if_needed(self):
        if self.filetype.name == 'Plain Text':
            # the user probably hasn't set the filetype
            self._guess_filetype()

    def _update_title(self):
        text = 'New File' if self.path is None else os.path.basename(self.path)
        if not self.is_saved():
            # TODO: figure out how to make the label red in ttk instead
            #       of stupid stars
            text = '*' + text + '*'

        if self in self.widget.parent:
            # the tab is in the tab manager
            self.config['text'] = text
        else:
            self.initial_options['text'] = text

    def _update_status(self, junk=None):
        if self.path is None:
            prefix = "New file"
        else:
            prefix = "File '%s'" % self.path
        line, column = self.textwidget.marks['insert']

        self.status = "%s, %s\tLine %s, column %s" % (
            prefix, self.filetype.name,
            line, column)

    def can_be_closed(self):
        """
        This overrides :meth:`Tab.can_be_closed` in order to display a
        save dialog.

        If the file has been saved, this returns True and the tab is
        closed normally. Otherwise this method asks the user whether the
        file should be saved, and returns False only if the user cancels
        something (and thus wants to keep working on this file).
        """
        if self.is_saved():
            return True

        if self.path is None:
            msg = "Do you want to save your changes?"
        else:
            msg = ("Do you want to save your changes to %s?"
                   % os.path.basename(self.path))

        answer = tk.dialog.yes_no_cancel("Close file", msg)
        if answer == 'cancel':
            return False
        if answer == 'yes':
            return self.save()
        if answer == 'no':
            # can be closed
            return True
        assert False    # pragma: no cover

    def on_focus(self):
        """This override of :meth:`Tab.on_focus` focuses the :attr:`textwidget\
`."""
        self.textwidget.focus()

    # TODO: returning None on errors kinda sucks, maybe a handle_errors kwarg?
    def save(self):
        """Save the file to the current :attr:`path`.

        This calls :meth:`save_as` if :attr:`path` is None, and returns
        False if the user cancels the save as dialog. None is returned
        on errors, and True is returned in all other cases. In other
        words, this returns True if saving succeeded.

        .. seealso:: :attr:`.on_save`
        """
        if self.path is None:
            return self.save_as()

        self.on_save.run()

        encoding = settings.get_section('General')['encoding']
        try:
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
        path = tk.dialog.save_file(**filetypes.get_filedialog_kwargs())
        if path is None:
            return False

        self.path = path
        self.save()
        return True

    # FIXME: don't ignore undo history :/
    def get_state(self):
        # e.g. "New File" tabs are saved even though the .path is None
        if self.is_saved() and self.path is not None:
            # this is really saved
            content = None
        else:
            content = self.textwidget.get()

        return (self.path, content, self._save_hash,
                tuple(self.textwidget.marks['insert']))

    @classmethod
    def from_state(cls, manager, state):
        path, content, save_hash, cursor_pos = state
        if content is None:
            # nothing has changed since saving, read from the saved file
            self = cls.open_file(manager, path)
        else:
            self = cls(manager, content, path)

        # the title depends on the saved hash
        self._save_hash = save_hash
        self._update_title()

        self.textwidget.marks['insert'] = cursor_pos
        self.textwidget.see(self.textwidget.marks['insert'])
        return self


if __name__ == '__main__':
    # test/demo
    window = tk.Window()

    tabmgr = TabManager(window)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.on_new_tab.connect(lambda tab: print("added tab", tab.i))
    tabmgr.bind('<<NotebookTabChanged>>',
                lambda: print("selected", tabmgr.selected_tab.i))

    def on_ctrl_w(event):
        if tabmgr.tabs():
            tabmgr.close_tab(tabmgr.select())

    window.bind('<Control-w>', on_ctrl_w)
    for keysym, callback in tabmgr.bindings:
        window.toplevel.bind(keysym, callback)

    import itertools
    def add_new_tab(counter=itertools.count(1)):
        tab = Tab(tabmgr)
        tab.i = next(counter)     # tabmgr doesn't care about this
        tab.title = "tab %d" % tab.i
        tabmgr.append_and_select(tab)

        text = tk.Text(tab.content)
        text.pack(fill='both', expand=True)
        text.insert(text.start, "this is the content of tab %d" % tab.i)

    tk.Button(window, text="add a new tab", command=add_new_tab).pack()
    add_new_tab(), add_new_tab(), add_new_tab(), add_new_tab(), add_new_tab()
    window.geometry(300, 200)
    tk.run()
