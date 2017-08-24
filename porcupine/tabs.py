r"""Tabs as in browser tabs, not \t characters."""

# Yes, I am aware of ``ttk.Notebook`` but it's way too limited for
# Porcupine. I can't even add a closing button or change the color of
# the top label.

import functools
import hashlib
import logging
import os
import tkinter
from tkinter import ttk, messagebox
import traceback

import porcupine
from porcupine import _dialogs, filetypes, textwidget, utils
from porcupine.settings import config

log = logging.getLogger(__name__)


class TabManager(ttk.Notebook):
    """A simple but awesome tab widget.

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

    .. attribute:: no_tabs_frame

        This widget is displayed when there are no tabs. By default,
        Porcupine adds a welcome message into this. You can remove the
        content of this frame and replace it with your own thing in a
        plugin, but **don't** set this to another widget like
        ``tabmanager.no_tabs_frame = something``.

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
    .. method:: forget(tab_id)
    .. method:: hide(tab_id)
    .. method:: identify(x, y)
    .. method:: index(tab_id)
    .. method:: insert(pos, child, **kw)
    .. method:: select(tab_id=None)
    .. method:: tab(tab_id, option=None, **kw)
    .. method:: tabs()
    .. method:: enable_traversal()

        Don't use these methods. Currently ``TabManager`` inherits from
        ``ttk.Notebook``, but that may be changed later. These methods
        come from ``ttk.Notebook``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bind('<<NotebookTabChanged>>', self._on_tab_selected, add=True)
        self.bind('<Button-1>', self._on_click, add=True)
        utils.bind_mouse_wheel(self, self._on_wheel, add=True)

        # TODO: use this somewhere
        self.no_tabs_frame = ttk.Frame(self)

        # These can be bound in a parent widget. This doesn't use
        # enable_traversal() because we want more bindings than it
        # creates.
        # TODO: document these
        partial = functools.partial     # pep-8 line length
        self.bindings = [
            ('<Control-Prior>', partial(self._on_page_updown, False)),
            ('<Control-Next>', partial(self._on_page_updown, False)),
            ('<Control-Shift-Prior>', partial(self._on_page_updown, True)),
            ('<Control-Shift-Next>', partial(self._on_page_updown, True)),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

    def _on_click(self, event):
        if self.identify(event.x, event.y) != 'label':
            # something else than the top label was clicked
            return

        # find the right edge of the label, hopefully there's no padding
        right = event.x
        while self.identify(right, event.y) == 'label':
            right += 1

        # the image is on the right edge of the label
        image_width = int(self.tk.call('image', 'width', 'img_closebutton'))
        if event.x + image_width >= right:
            # the close button was clicked
            tab = self.tabs[self.index('@%d,%d' % (event.x, event.y))]
            if tab.can_be_closed():
                self.close_tab(tab)

    def _on_page_updown(self, shifted, event):
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

    # tkinter's tabs() returns widget names (strings) instead of actual
    # widgets, this implementation str()'s everything anyway because
    # tkinter might be fixed some day
    @property
    def tabs(self):
        return [self.nametowidget(str(tab)) for tab in super().tabs()]

    @property
    def current_tab(self):
        if not self.select():
            return None
        return self.nametowidget(str(self.select()))

    @current_tab.setter
    def current_tab(self, tab):
        if tab is not None:
            self.select(tab)

    def _on_tab_selected(self, event):
        if self.current_tab is not None:
            self.current_tab.on_focus()
        self.event_generate('<<CurrentTabChanged>>')

    @property
    def current_index(self):
        if self.current_tab is None:
            return None
        return self.tabs.index(self.current_tab)

    @current_index.setter
    def current_index(self, index):
        if index not in range(self.index('end')):
            # this would create weird rollovers so maybe best to avoid
            raise IndexError
        self.select(index)

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

        # img_closebutton is from images/closebutton.gif, see
        # utils._init_images()
        self.add(tab, text=tab.title, image='img_closebutton',
                 compound='right')
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
        if tab is self.current_tab:
            # go to next or previous tab if possible
            self.select_right() or self.select_left()

        self.forget(tab)
        tab.destroy()

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

    def _swap(self, last_index):
        # it's important to move the second tab back instead of moving
        # the other tab forward because insert(number_of_tabs, tab)
        # doesn't work for some reason
        tab_string = self.tabs()[last_index]
        options = self.tab(last_index)
        self.forget(last_index)
        self.insert(last_index - 1, tab_string, **options)

    def move_left(self):
        """Move the current tab left if possible.

        Return True if the tab was moved.
        """
        if self.current_index in {None, 0}:
            return False
        self._swap(self.current_index)
        return True

    def move_right(self):
        """Like :meth:`move_left`, but moves right."""
        if self.current_index in {None, len(self.tabs)-1}:   # noqa
            return False
        self._swap(self.current_index + 1)
        return True

    def _on_alt_n(self, n, event):
        try:
            self.current_index = n - 1
            return 'break'
        except IndexError:
            pass


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

        def select_me(event):
            manager.current_tab = self

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
        try:
            self.master.tab(self, text=text)
        except tkinter.TclError:
            assert self not in self.master.tabs

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
    root = tkinter.Tk()
    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.bind('<<CurrentTabChanged>>',
                lambda event: print(repr(event.widget.current_tab)))

    ttk.Label(tabmgr.no_tabs_frame, text="u have no open tabs :(").pack()

    def on_ctrl_w(event):
        if tabmgr.tabs:    # current_tab is not None
            tabmgr.close_tab(tabmgr.current_tab)

    root.bind('<Control-w>', on_ctrl_w)
    for keysym, callback in tabmgr.bindings:
        root.bind(keysym, callback)

    for i in range(1, 6):
        tab = Tab(tabmgr)
        tab.title = "tab %d" % i
        tabmgr.add_tab(tab)

        # there's no ttk.Text 0_o
        text = tkinter.Text(tab)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)
        #utils.copy_bindings(tabmgr, text)

    root.mainloop()
