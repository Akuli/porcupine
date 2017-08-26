r"""Tabs as in browser tabs, not \t characters."""

# Yes, I am aware of ``ttk.Notebook`` but it's way too limited for
# Porcupine. I can't even add a closing button or change the color of
# the top label.

import functools
import hashlib
import itertools
import logging
import os
import tkinter
from tkinter import ttk, messagebox
import traceback

import porcupine
from porcupine import _dialogs, filetypes, textwidget, utils
from porcupine.settings import config

log = logging.getLogger(__name__)
_flatten = itertools.chain.from_iterable


class _Pane(ttk.Notebook):
    """One element of the split view."""

    def __init__(self, manager):
        super().__init__(manager)
        self.bind('<Button-1>', self._on_click, add=True)
        utils.bind_mouse_wheel(self, self._on_wheel, add=True)

    # tkinter's tabs() returns widget names (strings) instead of actual
    # widgets, this implementation str()'s everything anyway because
    # tkinter might be fixed some day
    def tabs(self):
        return tuple(self.nametowidget(str(tab)) for tab in super().tabs())

    # similar fix
    def select(self, tab_id=None):
        if tab_id is None:
            return self.nametowidget(str(super().select()))

        super().select(tab_id)
        return None

    # a customized version of add()
    def add_tab(self, tab):
        # img_closebutton is from images/closebutton.gif, see
        # utils._init_images()
        self.add(tab, text=tab.title, image='img_closebutton',
                 compound='right')
        tab.tkraise(self)      # make sure it's visible

    # this is lol
    def remove_tab(self, tab):
        self.forget(tab)
        if self.index('end') == 0:
            # no more tabs, get rid of this pane because a pane with no tabs
            # in it would suck... but first, can we select another pane?
            all_panes = self.master.panes()
            if len(all_panes) >= 2:
                try:
                    another_pane = all_panes[all_panes.index(self) + 1]
                except IndexError:
                    another_pane = all_panes[all_panes.index(self) - 1]
                another_pane.select().on_focus()
            else:
                # no, this is the last pane in the whole tab manager
                self.master._current_pane = None

            self.master.forget(self)
            self.destroy()

    # diff should be +1 for selecting a tab at right or -1 for left
    def select_next_to(self, diff):
        assert diff in {1, -1}, repr(diff)
        index = self.index(self.select())
        try:
            self.select(index + diff)
            return True
        except tkinter.TclError:   # should be "Slave index n out of bounds"
            return False

    def move_next_to(self, diff):
        assert diff in {1, -1}, repr(diff)
        i1 = self.index(self.select())
        i2 = i1 + diff
        if i1 > i2:
            i1, i2 = i2, i1

        if i1 < 0 or i2 >= self.index('end'):
            return False

        # it's important to move the second tab back instead of moving
        # the other tab forward because insert(number_of_tabs, tab)
        # doesn't work for some reason
        tab = self.tabs()[i2]
        options = self.tab(i2)
        selected = (tab is self.select())    # TODO: optimize-cleanup?

        self.forget(i2)
        self.insert(i1, tab, **options)
        if selected:
            self.select(tab)

        return True

    def _on_click(self, event):
        if self.identify(event.x, event.y) != 'label':
            # something else than the top label was clicked
            return

        # find the right edge of the label
        right = event.x
        while self.identify(right, event.y) == 'label':
            right += 1

        # hopefully the image is on the right edge of the label and
        # there's no padding :O
        image_width = int(self.tk.call('image', 'width', 'img_closebutton'))
        if event.x + image_width >= right:
            # the close button was clicked
            tab = self.tabs()[self.index('@%d,%d' % (event.x, event.y))]
            if tab.can_be_closed():
                # self.master is the tab manager
                self.master.close_tab(tab)

    def _on_wheel(self, direction):
        diffs = {'up': -1, 'down': +1}
        self.select_next_to(diffs[direction])


class TabManager(ttk.PanedWindow):
    """A simple but awesome tab widget.

    This widget is a lot like ``ttk.Notebook``, but this class also
    implements split views and only :class:`Tab` can be added to this.

    .. virtualevent:: NewTab

        This runs after a new tab has been added to this tab manager
        with :meth:`~add_tab`. The tab is always added to the end of
        :attr:`~tabs`, so you can access it with
        ``event.widget.tabs[-1]``.

        Bind to the ``<Destroy>`` event of the tab if you want to clean
        up something when the tab is closed.

    .. virtualevent:: CurrentTabChanged

        This runs when the user selects another tab or Porcupine does it
        for some reason. Use ``event.widget.current_tab`` to get or set
        the currently selected tab.

        .. seealso:: :attr:`~current_tab`

    .. attribute:: tabs

        List of Tab objects in the tab manager.

        Don't modify this list yourself, use methods like
        :meth:`~move_left`, :meth:`~move_right`, :meth:`~add_tab` or
        :meth:`~close_tab` instead.

    .. attribute:: current_tab

        The tab that the user has currently selected.

        This is None when there are no tabs. You can set this to select
        a tab, like this::

            tabmanager.current_tab = some_tab

    .. attribute:: current_index

        .. warning:: Don't use this attribute. I may remove it later.

        The index of :attr:`~current_tab` in :attr:`~tabs`.

        Setting this raises :exc:`IndexError` if the index is too big or
        too small. Negative indexes are not supported.

    .. method:: add(child, **kw)
    .. method:: insert(pos, child, **kw)
    .. method:: pane(pane, option=None, **kw)
    .. method:: panecget(child, option)
    .. method:: paneconfig(tagOrId, cnf=None, **kw)
    .. method:: paneconfigure(tagOrId, cnf=None, **kw)
    .. method:: panes()
    .. method:: proxy(*args)
    .. method:: proxy_coord()
    .. method:: proxy_forget()
    .. method:: proxy_place(x, y)
    .. method:: remove(child)
    .. method:: sash(*args)
    .. method:: sash_coord(index)
    .. method:: sash_mark(index)
    .. method:: sash_place(index, x, y)
    .. method:: sashpos(index, newpos=None)

        Don't use these methods. Currently ``TabManager`` inherits from
        ``ttk.PanedWindow``, but that may be changed later. These methods
        come from ``PanedWindow``.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('orient', 'horizontal')
        super().__init__(*args, **kwargs)
        self._current_pane = None

        # These can be bound in a parent widget. This doesn't use
        # enable_traversal() because we want more bindings than it
        # creates.
        # TODO: document these?
        partial = functools.partial     # pep-8 line length
        self.bindings = [
            ('<Control-Prior>', partial(self._on_page_updown, False, -1)),
            ('<Control-Next>', partial(self._on_page_updown, False, +1)),
            ('<Control-Shift-Prior>', partial(self._on_page_updown, True, -1)),
            ('<Control-Shift-Next>', partial(self._on_page_updown, True, +1)),
            ('<Alt-Left>', partial(self._on_alt_arrow, False, -1)),
            ('<Alt-Right>', partial(self._on_alt_arrow, False, +1)),
            ('<Shift-Alt-Left>', partial(self._on_alt_arrow, True, -1)),
            ('<Shift-Alt-Right>', partial(self._on_alt_arrow, True, +1)),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

        # this bind all <FocusIn> events of the window that the tab
        # manager is in
        self.winfo_toplevel().bind(
            '<FocusIn>', self._on_maybe_pane_selected, add=True)

    def _on_page_updown(self, shifted, diff, event):
        if self._current_pane is not None:
            if shifted:
                self._current_pane.move_next_to(diff)
            else:
                self._current_pane.select_next_to(diff)
        return 'break'

    def _on_alt_arrow(self, shifted, diff, event):
        if self._current_pane is None:
            # no tabs
            assert not self.panes(), "_current_tab wasn't set correctly"
            return 'break'

        if shifted:
            self._move_to_another_pane(diff)
        else:
            # select another pane
            panes = self.panes()    # superstitious optimizations ftw
            current_index = panes.index(self._current_pane)
            new_index = current_index + diff
            panes[new_index % len(panes)].select().on_focus()

        return 'break'

    def _on_alt_n(self, n, event):
        try:
            self.current_tab = self.tabs[n - 1]
            return 'break'
        except IndexError:
            return None

    # similar fix as in _Pane
    def panes(self):
        return tuple(self.nametowidget(str(pane)) for pane in super().panes())

    def _add_pane(self, initial_tab, where='end'):
        if where == len(self.panes()):
            # yes, this is needed
            where = 'end'

        pane = _Pane(self)
        pane.bind('<<NotebookTabChanged>>', self._on_tab_selected, add=True)
        pane.add_tab(initial_tab)
        self.insert(where, pane, weight=1)

    def _on_maybe_pane_selected(self, event):
        for pane in self.panes():
            if str(event.widget).startswith(str(pane.select()) + '.'):
                # something in the pane's current tab was selected
                if self._current_pane is not pane:
                    self._current_pane = pane
                    self.event_generate('<<CurrentTabChanged>>')
                break

    def _on_tab_selected(self, event):
        if event.widget is self._current_pane:
            event.widget.select().on_focus()
            self.event_generate('<<CurrentTabChanged>>')

    @property
    def tabs(self):
        return list(_flatten(pane.tabs() for pane in self.panes()))

    @property
    def current_tab(self):
        if self._current_pane is None:
            assert not self.panes(), "_current_pane wasn't set correctly"
            return None
        return self._current_pane.select()

    @current_tab.setter
    def current_tab(self, tab):
        for pane in self.panes():
            if tab in pane.tabs():
                pane.select(tab)
                tab.on_focus()
                return

        raise ValueError("unknown tab %r" % (tab,))

    def add_tab(self, tab, make_current=True):
        """Append a :class:`.Tab` to this tab manager.

        If ``tab.equivalent(existing_tab)`` returns True for any
        ``existing_tab`` that is already in the tab manager, then that
        existing tab is returned. Otherwise *tab* is added to the tab
        manager and returned.

        If *make_current* is True, then :attr:`current_tab` is set to
        the tab that is returned.

        .. seealso::
            The :meth:`.Tab.equivalent` and :meth:`~close_tab` methods.
        """
        assert tab not in self.tabs, "cannot add the same tab twice"
        for existing_tab in self.tabs:
            if tab.equivalent(existing_tab):
                if make_current:
                    self.current_tab = existing_tab
                return existing_tab

        if self.panes():
            # FIXME: the tab shouldn't be guaranteed to be the last tab
            # in self.tabs -_-
            self._current_pane = self.panes()[-1]
            self._current_pane.add_tab(tab)
        else:
            self._add_pane(tab)

        if make_current:
            self.current_tab = tab

        # the update() is needed in some cases because virtual events
        # don't run if the widget isn't visible yet
        self.update()
        self.event_generate('<<NewTab>>')
        return tab

    def close_tab(self, tab):
        """Destroy a tab without calling :meth:`~Tab.can_be_closed`.

        The closed tab cannot be added back to the tab manager later.

        .. seealso:: The :meth:`.Tab.can_be_closed` method.
        """
        # which pane is this tab in?
        for pane in self.panes():
            if tab in pane.tabs():
                break
        else:
            raise ValueError("unknown tab " + repr(tab))

        pane.remove_tab(tab)     # may get rid of the whole pane
        tab.destroy()

    # moves the current tab to another pane, creating a new pane if needed
    def _move_to_another_pane(self, diff):
        """Move the currently selected tab to another pane.

        The diff should be +1 for moving right or -1 for moving left.
        New panes are created automatically when needed.
        """
        assert diff in {+1, -1}, repr(diff)
        panes = self.panes()    # superstitious optimizations ftw
        current_index = panes.index(self._current_pane)
        tab = self._current_pane.select()

        if (current_index + diff) in range(len(panes)):
            # remove_tab() will get rid of the whole pane if it contains
            # only one tab, so it's important NOT to update panes to the
            # new value of self.panes() (without changing the index)
            self._current_pane.remove_tab(tab)
            panes[current_index + diff].add_tab(tab)
            panes[current_index + diff].select(tab)
            tab.on_focus()

        elif len(self._current_pane.tabs()) == 1:
            # corner case: if there's just one tab in the pane then
            # moving it to a new pane would do nothing but create
            # more corner cases :D yay, corner cases
            pass

        else:
            # create a new pane
            self._current_pane.remove_tab(tab)   # FIXME !!!!
            if diff == 1:
                self._add_pane(tab, current_index + 1)
            else:
                self._add_pane(tab, current_index)
            tab.on_focus()    # FIXME: this doesn't work 0_o very weird


# tabs are initialized into the tab manager, but adding them to a pane
# in the tab manager still works
class Tab(ttk.Frame):
    r"""Base class for widgets that can be added to TabManager.

    You can easily create custom kinds of tabs by inheriting from this
    class. Here's a very minimal but complete example plugin::

        import tkinter as tk
        import porcupine
        from porcupine import tabs

        class HelloTab(tabs.Tab):
            def __init__(self, manager):
                super().__init__(manager)
                self.title = "Hello"
                tk.Label(self, text="Hello World!").pack()

        def new_hello_tab():
            manager = porcupine.get_tab_manager()
            manager.add_tab(HelloTab(manager))

        def setup():
            porcupine.add_action(new_hello_tab, 'Hello/New Hello Tab')

    .. virtualevent:: StatusChanged

        This event is generated when :attr:`status` is set to a new
        value. Use ``event.widget.status`` to access the current status.

    .. attribute:: status

        A human-readable string for showing in e.g. a status bar.

        The status message can also contain multiple tab-separated
        things, e.g. ``"File 'thing.py'\tLine 12, column 34"``.

        This is ``''`` by default, but that can be changed like
        ``tab.status = something_new``.

        If you're writing something like a status bar, make sure to
        handle ``\t`` characters and bind :virtevt:`~StatusChanged`.

    .. attribute:: master

        Tkinter sets this to the parent widget. Use this attribute to
        access the :class:`TabManager` of a tab.

    .. attribute:: title

        This is the title of the tab, next to the red close button. You
        can set and get this attribute easily.
    """

    def __init__(self, manager):
        super().__init__(manager)
        self._status = ''
        self._title = ''

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, new_status):
        self._status = new_status
        self.event_generate('<<StatusChanged>>')

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, text):
        self._title = text

        # this is here because accessing _non_public tab manager methods
        # from here wouldn't be good style (lol)
        for pane in self.master.panes():
            if self in pane.tabs():
                pane.tab(self, text=text)
                break

    def can_be_closed(self):
        """
        This is usually called before the tab is closed. The tab
        shouldn't be closed if this returns False.

        By default, this always returns True, but you can override this
        in a subclass to do something more interesting. See
        :meth:`.FileTab.can_be_closed` for an example.
        """
        return True

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

    The tab will have content in it by default when it’s opened. If
    *path* is given, the file will be saved there when Ctrl+S is
    pressed. Otherwise this becomes a "New File" tab.

    For example, you can open a file from a path like this::

        from porcupine import tabs, utils
        from porcupine.settings import config

        with open(your_path, 'r', encoding=config['Files', 'encoding']) \
as file:
            content = file.read()

        tabmanager = utils.get_tab_manager()
        tab = tabs.FileTab(tabmanager, content, path=your_path)
        tabmanager.add_tab(tab)

    .. virtualevent:: PathChanged

        This runs when :attr:`~path` is set to a new value. Use
        ``event.widget.path`` to get the new path.

    .. virtualevent:: FiletypeChanged

        Like :virtevt:`~PathChanged`, but for :attr:`~filetype`. Use
        ``event.widget.filetype`` to access the new file type.

    .. attribute:: textwidget

        The central text widget of the tab.

        Currently this is a :class:`porcupine.textwidget.MainText`, but
        this is guaranteed to always be a
        :class:`HandyText <porcupine.textwidget.HandyText>`.

    .. attribute:: path

        Path to where this file is currently saved, as a string.

        This is None if the file has never been saved, and otherwise
        this should be always set to an absolute path.

    .. attribute:: filetype

        A value from :data:`porcupine.filetypes.filetypes`.

        Setting this runs :virtevt:`~FiletypeChanged`.
    """

    def __init__(self, manager, content='', *, path=None):
        super().__init__(manager)

        self._save_hash = None

        # path and filetype are set correctly below
        # TODO: try to guess the filetype from the content when path is None
        self._path = path
        self._guess_filetype()          # this sets self._filetype
        self.bind('<<PathChanged>>', self._update_top_label, add=True)
        self.bind('<<PathChanged>>', self._guess_filetype, add=True)

        # FIXME: wtf is this doing here?
        self.mainframe = ttk.Frame(self)
        self.mainframe.pack(fill='both', expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        # TODO: document this
        self.textwidget = textwidget.MainText(
            self.mainframe, self._filetype, width=1, height=1,
            wrap='none', undo=True)
        self.bind('<<FiletypeChanged>>',
                  lambda event: self.textwidget.set_filetype(self.filetype),
                  add=True)
        self.textwidget.bind('<<ContentChanged>>', self._update_top_label,
                             add=True)

        if content:
            self.textwidget.insert('1.0', content)
            self.textwidget.edit_reset()   # reset undo/redo

        self.bind('<<PathChanged>>', self._update_status, add=True)
        self.bind('<<FiletypeChanged>>', self._update_status, add=True)
        self.textwidget.bind('<<CursorMoved>>', self._update_status, add=True)

        # everything seems to work ok without this except that e.g.
        # pressing Ctrl+O in the text widget opens a file AND inserts a
        # newline (Tk inserts a newline by default)
        utils.copy_bindings(porcupine.get_main_window(), self.textwidget)

        # the scrollbar is exposed for things like line numbers, see
        # plugins/linenumbers.py
        self.scrollbar = ttk.Scrollbar(self.mainframe)
        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

        # these are packed right-to-left because the linenumbers are at
        # left and can be pack_forgot()ten
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget.pack(side='right', fill='both', expand=True)

        self.mark_saved()
        self._update_top_label()
        self._update_status()

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
        """Make :meth:`is_saved` return True."""
        self._save_hash = self._get_hash()
        self._update_top_label()      # TODO: add a virtual event for this?

    def is_saved(self):
        """Return False if the text has changed since previous save.

        This is set to False automagically when the content is modified.
        Use :meth:`mark_saved` to set this to True.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self):
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
            self.event_generate('<<PathChanged>>')

    @property
    def filetype(self):
        return self._filetype

    @filetype.setter
    def filetype(self, filetype):
        assert filetype in filetypes.filetypes.values()
        self._filetype = filetype
        self.event_generate('<<FiletypeChanged>>')

    def _guess_filetype(self, junk=None):
        if self.path is None:
            # there's no way to "unsave a file", but a plugin might do
            # that for whatever reason
            self.filetype = filetypes.filetypes['Text only']
        else:
            self.filetype = filetypes.guess_filetype(self.path)

    def _update_top_label(self, junk=None):
        text = 'New File' if self.path is None else os.path.basename(self.path)
        if not self.is_saved():
            # TODO: figure out how to make the label red in ttk instead
            # of stupid stars
            text = '*' + text + '*'
        self.title = text

    def _update_status(self, junk=None):
        if self.path is None:
            start = "New file"
        else:
            start = "File '%s'" % self.path
        line, column = self.textwidget.index('insert').split('.')

        self.status = "%s, %s\tLine %s, column %s" % (
            start, self.filetype.name, line, column)

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
        answer = messagebox.askyesnocancel("Close file", msg)
        if answer is None:
            # cancel
            return False
        if answer:
            # yes
            return self.save()
        # no was clicked, can be closed
        return True

    # TODO: document the overriding
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
        path = _dialogs.save_as(self.path)
        if path is None:
            return False
        self.path = path
        self.save()
        return True


if __name__ == '__main__':
    # test/demo
    from porcupine.utils import _init_images
    root = tkinter.Tk()
    _init_images()

    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.bind('<<NewTab>>',
                lambda event: print("added tab", tabmgr.tabs[-1].i),
                add=True)
    tabmgr.bind('<<CurrentTabChanged>>',
                lambda event: print("selected", event.widget.current_tab.i),
                add=True)

    def on_ctrl_w(event):
        if tabmgr.tabs:    # current_tab is not None
            tabmgr.close_tab(tabmgr.current_tab)

    root.bind('<Control-w>', on_ctrl_w)
    for keysym, callback in tabmgr.bindings:
        root.bind(keysym, callback)

    def add_new_tab(counter=itertools.count(1)):
        tab = Tab(tabmgr)
        tab.i = next(counter)     # tabmgr doesn't care about this
        tab.title = "tab %d" % tab.i
        tabmgr.add_tab(tab)

        text = tkinter.Text(tab)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % tab.i)

    ttk.Button(root, text="add a new tab", command=add_new_tab).pack()
    add_new_tab(), add_new_tab(), add_new_tab(), add_new_tab(), add_new_tab()
    root.geometry('300x200')
    root.mainloop()
