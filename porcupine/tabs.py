r"""Tabs as in browser tabs, not \t characters."""

import functools
import hashlib
import importlib
import itertools
import logging
import pathlib
import tkinter
from tkinter import ttk, messagebox, filedialog
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

import pygments.lexer     # type: ignore
import pygments.lexers    # type: ignore

from porcupine import filetypes, images, settings, textwidget, utils


log = logging.getLogger(__name__)
_flatten = itertools.chain.from_iterable


class TabManager(ttk.Notebook):
    """A simple but awesome tab widget.

    This widget inherits from ``ttk.Notebook``. All widgets added to
    this should be :class:`Tab` objects.

    .. virtualevent:: NewTab

        This runs when a new tab has been added to the tab manager with
        :meth:`add_tab`. Use :func:`~porcupine.utils.bind_with_data` and
        ``event.data_widget()`` to access the tab that was added.

        Bind to the ``<Destroy>`` event of the tab if you want to clean
        up something when the tab is closed.

    .. virtualevent:: WillOpenFile

        :meth:`FileTab.open_file` generates this event when an **existing**
        file is about to be opened. Unlike :virtevt:`~NewTab`, this never runs
        for tabs created without :meth:`~FileTab.open_file`, such as the tabs
        created by clicking "New File" in the menu.

        Use :func:`~porcupine.utils.bind_with_data` and ``event.data_widget()``
        to access the related :class:`FileTab`.

        This event runs before the file is read, so if you want your plugin to
        e.g. decide which encoding will be used, then this is the virtual event
        that you should use. See :source:`porcupine/plugins/editorconfig.py`
        for an example.

        .. note::
            :virtevt:`WillOpenFile` doesn't run for files created by clicking
            "New File" and then "Save as". Use  :virtevt:`NewTab` and
            :virtevt:`~FileTab.PathChanged` to handle those.

    .. virtualevent:: NotebookTabChanged

        This runs when the user selects another tab or Porcupine does it
        for some reason. Use ``event.widget.select()`` to get the
        currently selected tab.

        This virtual event has ``Notebook`` prefixed in its name because
        it's inherited from ``ttk.Notebook`` and whoever created it
        wanted to add some boilerplate. I think something like
        ``<<SelectedTabChanged>>`` would be a better name.

        .. seealso:: :meth:`select`

    .. method:: add(child, **kw)
    .. method:: enable_traversal()
    .. method:: forget(tab_id)
    .. method:: hide(tab_id)
    .. method:: insert(pos, child, **kw)
    .. method:: tab(tab_id, option=None, **kw)

        Don't use these methods. They are inherited from
        ``ttk.Notebook``, and :class:`TabManager` has other methods for
        doing what is usually done with these methods.

        .. seealso::
            :meth:`add_tab`, :meth:`close_tab`, :attr:`Tab.title`
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # These can be bound in a parent widget. This doesn't use
        # enable_traversal() because we want more bindings than it
        # creates.
        # TODO: document self.bindings?
        self.bindings: List[Tuple[str, Callable[[tkinter.Event], utils.BreakOrNone]]] = [
            ('<Control-Prior>', functools.partial(self._on_page_updown, False, -1)),
            ('<Control-Next>', functools.partial(self._on_page_updown, False, +1)),
            ('<Control-Shift-Prior>', functools.partial(self._on_page_updown, True, -1)),
            ('<Control-Shift-Next>', functools.partial(self._on_page_updown, True, +1)),
        ]
        for number in range(1, 10):
            callback = functools.partial(self._on_alt_n, number)
            self.bindings.append(('<Alt-Key-%d>' % number, callback))

        self.bind('<<NotebookTabChanged>>', self._focus_selected_tab, add=True)
        self.bind('<Button-1>', self._on_click, add=True)
        utils.bind_mouse_wheel(self, self._on_wheel, add=True)

    def _focus_selected_tab(self, event: tkinter.Event) -> None:
        tab = self.select()
        if tab is not None:
            tab.on_focus()

    def _on_click(self, event: tkinter.Event) -> None:
        if self.identify(event.x, event.y) != 'label':
            # something else than the top label was clicked
            return

        # find the right edge of the label
        right = event.x
        while self.identify(right, event.y) == 'label':
            right += 1

        # hopefully the image is on the right edge of the label and
        # there's no padding :O
        if event.x + images.get('closebutton').width() >= right:
            # the close button was clicked
            tab = self.tabs()[self.index('@%d,%d' % (event.x, event.y))]
            if tab.can_be_closed():
                self.close_tab(tab)

    def _on_wheel(self, direction: str) -> None:
        self.select_another_tab({'up': -1, 'down': +1}[direction])

    def _on_page_updown(
            self, shifted: bool, diff: int,
            event: tkinter.Event) -> utils.BreakOrNone:
        if shifted:
            self.move_selected_tab(diff)
        else:
            self.select_another_tab(diff)
        return 'break'

    def _on_alt_n(self, n: int, event: tkinter.Event) -> utils.BreakOrNone:
        try:
            self.select(n - 1)
            return 'break'
        except tkinter.TclError:        # index out of bounds
            return None

    # fixing tkinter weirdness: some methods returns widget names as
    # strings instead of widget objects, these str() everything anyway
    # because tkinter might be fixed some day
    #
    # The ignore comment is to allow creating someting incompatible with
    # ttk.Notebook. Hopefully it doesn't break any ttk.Notebook internals.
    def select(self, tab_id: Union[None, int, 'Tab'] = None) -> Optional['Tab']:  # type: ignore
        """Select the given tab as if the user clicked it.

        Usually the ``tab_id`` should be a :class:`.Tab` widget. If it is not
        given, this returns the currently selected tab or None if there are no
        tabs.
        """
        if tab_id is None:
            selected = super().select()
            if not selected:        # no tabs, selected == ''
                return None
            return cast(Tab, self.nametowidget(str(selected)))

        # the tab can be e.g. an index, that's why two super() calls
        super().select(tab_id)
        return None

    def tabs(self) -> Tuple['Tab', ...]:
        """Return a tuple of tabs in the tab manager.

        This returns a tuple instead of a list for compatibility with
        tkinter.
        """
        # tkinter has a bug that makes the original tabs() return widget name
        # strings instead of widget objects, and this str()'s the tabs just in
        # case it is fixed later: str(widget object) and str(widget name) both
        # give the widget name consistently
        return tuple(cast(Tab, self.nametowidget(str(tab)))
                     for tab in super().tabs())

    def add_tab(self, tab: 'Tab', select: bool = True) -> 'Tab':
        """Append a :class:`.Tab` to this tab manager.

        If ``tab.equivalent(existing_tab)`` returns True for any
        ``existing_tab`` that is already in the tab manager, then that
        existing tab is returned. Otherwise *tab* is added to the tab
        manager and returned.

        If *select* is True, then the returned tab is selected
        with :meth:`~select`.

        .. seealso::
            The :meth:`.Tab.equivalent` and :meth:`~close_tab` methods.
        """
        assert tab not in self.tabs(), "cannot add the same tab twice"
        for existing_tab in self.tabs():
            if tab.equivalent(existing_tab):
                if select:
                    self.select(existing_tab)
                return existing_tab

        self.add(tab, text=tab.title, image=images.get('closebutton'),
                 compound='right')
        if select:
            self.select(tab)

        # The update() is needed in some cases because virtual events don't run
        # if the widget isn't visible yet.
        self.update()
        self.event_generate('<<NewTab>>', data=tab)
        return tab

    def close_tab(self, tab: 'Tab') -> None:
        """Destroy a tab without calling :meth:`~Tab.can_be_closed`.

        The closed tab cannot be added back to the tab manager later.

        .. seealso:: The :meth:`.Tab.can_be_closed` method.
        """
        self.forget(tab)
        tab.destroy()

    def select_another_tab(self, diff: int) -> bool:
        """Try to select another tab next to the currently selected tab.

        *diff* should be ``1`` for selecting a tab at right or ``-1``
        for left. This returns True if another tab was selected and
        False if the current tab is already the leftmost tab or there
        are no tabs.
        """
        assert diff in {1, -1}, repr(diff)
        if not self.tabs():
            return False

        selected_tab = self.select()
        assert selected_tab is not None
        index = self.index(selected_tab)

        try:
            self.select(index + diff)
            return True
        except tkinter.TclError:   # should be "Slave index n out of bounds"
            return False

    # TODO: test this
    def move_selected_tab(self, diff: int) -> bool:
        """Try to move the currently selected tab left or right.

        *diff* should be ``1`` for moving to right or ``-1`` for left.
        This returns True if the tab was moved and False if there was no
        room for moving it or there are no tabs.
        """
        assert diff in {1, -1}, repr(diff)
        if not self.tabs():
            return False

        selected_tab = self.select()
        assert selected_tab is not None
        i1 = self.index(selected_tab)

        # this could be simplified, but it's nice and readable now
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
        selected = (tab is self.select())

        # type ignore comment because mypy support for **kwargs is not great
        self.forget(i2)
        self.insert(i1, tab, **options)     # type: ignore
        if selected:
            self.select(tab)

        return True


# _FileTabT represents a subclass of FileTab. Don't know if there's a better
# way to tell that to mypy than passing FileTab twice...
_TabT = TypeVar('_TabT', 'Tab', 'Tab')
_FileTabT = TypeVar('_FileTabT', 'FileTab', 'FileTab')


class Tab(ttk.Frame):
    r"""Base class for widgets that can be added to TabManager.

    You can easily create custom kinds of tabs by inheriting from this
    class. Here's a very minimal but complete example plugin::

        from tkinter import ttk
        from porcupine import actions, get_tab_manager, tabs

        class HelloTab(tabs.Tab):
            def __init__(self, manager):
                super().__init__(manager)
                self.title = "Hello"
                ttk.Label(self, text="Hello World!").pack()

        def new_hello_tab():
            get_tab_manager().add_tab(HelloTab(get_tab_manager()))

        def setup():
            actions.add_command('Hello/New Hello Tab', new_hello_tab)

    Note that you need to use the pack geometry manager when creating
    custom tabs. If you want to use grid or place you can create a frame
    inside the tab, pack it with ``fill='both', expand=True`` and do
    whatever you want inside it.

    .. virtualevent:: StatusChanged

        This event is generated when :attr:`status` is set to a new
        value. Use ``event.widget.status`` to access the current status.

    .. attribute:: title

        This is the title of the tab, next to the red close button. You
        can set and get this attribute easily.

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

    .. attribute:: top_frame
    .. attribute:: bottom_frame
    .. attribute:: left_frame
    .. attribute:: right_frame

        These are ``ttk.Frame`` widgets that are packed to each side of
        the frame. Plugins add different kinds of things to these, for
        example, :source:`the statusbar <porcupine/plugins/statusbar.py>`
        is a widget in ``bottom_frame``.

        These frames should contain no widgets when Porcupine is running
        without plugins. Use pack when adding things here.
    """
    # TODO: write types into above docstring

    master: TabManager

    def __init__(self, manager: TabManager) -> None:
        super().__init__(manager)
        self._status = ''
        self._title = ''

        # top and bottom frames must be packed first because this way
        # they extend past other frames in the corners
        self.top_frame = ttk.Frame(self)
        self.bottom_frame = ttk.Frame(self)
        self.left_frame = ttk.Frame(self)
        self.right_frame = ttk.Frame(self)
        self.top_frame.pack(side='top', fill='x')
        self.bottom_frame.pack(side='bottom', fill='x')
        self.left_frame.pack(side='left', fill='y')
        self.right_frame.pack(side='right', fill='y')

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, new_status: str) -> None:
        self._status = new_status
        self.event_generate('<<StatusChanged>>')

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, text: str) -> None:
        self._title = text
        if self in self.master.tabs():
            self.master.tab(self, text=text)

    def can_be_closed(self) -> bool:
        """
        This is usually called before the tab is closed. The tab
        shouldn't be closed if this returns False.

        By default, this always returns True, but you can override this
        in a subclass to do something more interesting. See
        :meth:`.FileTab.can_be_closed` for an example.
        """
        return True

    def on_focus(self) -> None:
        """This is called when the tab is selected.

        This does nothing by default. You can override this in a
        subclass and make this focus the tab's main widget if needed.
        """

    def equivalent(self, other: 'Tab') -> bool:
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

    def get_state(self) -> Optional[Any]:
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
    def from_state(
            cls: Type[_TabT], manager: TabManager, state: Any) -> _TabT:
        """
        Create a new tab from the return value of :meth:`get_state`.
        Be sure to override this if you override :meth:`get_state`.
        """
        raise NotImplementedError(
            "from_state() wasn't overrided but get_state() was overrided")


_FileTabState = Tuple[
    Optional[pathlib.Path],
    Optional[str],   # content
    Optional[str],   # hash
    str,             # cursor location
]


def _import_lexer_class(name: str) -> pygments.lexer.LexerMeta:
    modulename, classname = name.rsplit('.', 1)
    module = importlib.import_module(modulename)
    klass = getattr(module, classname)
    if not isinstance(klass, pygments.lexer.LexerMeta):
        raise TypeError(f"expected a Lexer subclass, got {klass}")
    return klass


class FileTab(Tab):
    """A subclass of :class:`.Tab` that represents an opened file.

    The filetab will have *content* in it by default when it's opened. If
    *path* is given, the file will be saved there when Ctrl+S is
    pressed. Otherwise this becomes a "New File" tab.

    If you want to open a new tab for editing an existing file,
    use :meth:`open_file`.

    .. virtualevent:: PathChanged

        This runs when :attr:`~path` is set to a new value. Use
        ``event.widget.path`` to get the new path.

        When the file is saved with :meth:`save_as`, the :virtevt:`PathChanged`
        event callbacks run before the file is written, so you can e.g. change
        the encoding setting in a :virtevt:`PathChanged` callback.

    .. attribute:: settings
        :type: porcupine.settings.Settings

        This setting object is for settings loaded from :mod:`porcupine.filetypes`,
        but they can be changed file-specifically too.
        It contains the following settings by default (but plugins add more
        settings with :meth:`~porcupine.settings.Settings.add_option`):

            ``pygments_lexer``: a subclass of :class:`pygments.lexer.Lexer`

            ``tabs2spaces``: :class:`bool`

            ``indent_size``: :class:`int`

            ``encoding``: :class:`str`

        See :source:`porcupine/default_filetypes.toml` for a description of
        each option.

    .. virtualevent:: TabSettingChanged:foo

        When the ``title`` of :attr:`~settings` is set,
        the tab receives (but the child widgets of the tab don't receive)
        a virtual event named ``<<TabSettingChanged:title>>``.
        This works similarly for other tab settings.

    .. virtualevent:: Save

        This runs before the file is saved with the :meth:`save` method.

    .. attribute:: textwidget
        :type: porcupine.textwidget.MainText

        The central text widget of the tab.

        When a new :class:`FileTab` is created, these functions will be called
        for the text widget:

            * :func:`porcupine.textwidget.use_pygments_theme`
            * :func:`porcupine.textwidget.track_changes`

    .. attribute:: scrollbar
        :type: tkinter.ttk.Scrollbar

        This is the scrollbar next to :attr:`.textwidget`.

        Things like :source:`the line number plugin <porcupine/plugins/linenum\
bers.py>` use this attribute.

    .. attribute:: path
        :type: Optional[pathlib.Path]

        The path where this file is currently saved.

        This is None if the file has never been saved, and otherwise
        an absolute path.

        .. seealso:: The :virtevt:`PathChanged` virtual event.
    """

    def __init__(self, manager: TabManager, content: str = '',
                 path: Optional[pathlib.Path] = None,
                 filetype: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(manager)

        self._save_hash: Optional[str] = None
        if path is None:
            self._path = None
        else:
            self._path = path.absolute()

        self.settings = settings.Settings(self, '<<TabSettingChanged:{}>>')
        self.settings.add_option(
            'pygments_lexer',
            pygments.lexers.TextLexer,
            type=pygments.lexer.LexerMeta,
            converter=_import_lexer_class)
        self.settings.add_option('encoding', 'utf-8')
        self.settings.add_option('tabs2spaces', True)
        self.settings.add_option('indent_size', 4)

        if filetype is None:
            self._guess_filetype()
        else:
            self.filetype_to_settings(filetype)
        self.bind('<<PathChanged>>', self._guess_filetype, add=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self, width=1, height=1, wrap='none', undo=True)
        self.textwidget.pack(side='left', fill='both', expand=True)
        self.textwidget.bind('<<ContentChanged>>', self._update_title,
                             add=True)

        if content:
            self.textwidget.insert('1.0', content)
            self.textwidget.edit_reset()   # reset undo/redo

        self.bind('<<PathChanged>>', self._update_status, add=True)
        self.textwidget.bind('<<CursorMoved>>', self._update_status, add=True)

        self.scrollbar = ttk.Scrollbar(self.right_frame)
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

        self.mark_saved()
        self._update_title()
        self._update_status()

    @classmethod
    def open_file(cls: Type[_FileTabT], manager: TabManager, path: pathlib.Path) -> _FileTabT:
        """Read a file and return a new FileTab object.

        Use this constructor if you want to open an existing file from a
        path and let the user edit it.

        :exc:`UnicodeError` or :exc:`OSError` is raised if reading the
        file fails.
        """
        tab = cls(manager, path=path)
        manager.event_generate('<<WillOpenFile>>', data=tab)
        with path.open('r', encoding=tab.settings.get('encoding', str)) as file:
            content = file.read()
        tab.textwidget.insert('1.0', content)

        tab.mark_saved()
        return tab

    def equivalent(self, other: Tab) -> bool:    # override
        # this used to have hasattr(other, "path") instead of isinstance
        # but it screws up if a plugin defines something different with
        # a path attribute, for example, a debugger plugin might have
        # tabs that represent files and they might need to be opened at
        # the same time as FileTabs are
        return (isinstance(other, FileTab) and
                self.path is not None and
                other.path is not None and
                self.path.samefile(other.path))

    # TODO: avoid doing this on every keypress?
    def _get_hash(self) -> str:
        result = hashlib.md5(self.textwidget.get('1.0', 'end - 1 char').encode('utf-8'))

        # hash objects don't define an __eq__ so we need to use a string
        # representation of the hash
        return result.hexdigest()

    def mark_saved(self) -> None:
        """Make :meth:`is_saved` return True."""
        self._save_hash = self._get_hash()
        self._update_title()

    def is_saved(self) -> bool:
        """Return False if the text has changed since previous save.

        This is set to False automagically when the content is modified.
        Use :meth:`mark_saved` to set this to True.
        """
        return self._get_hash() == self._save_hash

    @property
    def path(self) -> Optional[pathlib.Path]:
        return self._path

    @path.setter
    def path(self, new_path: Optional[pathlib.Path]) -> None:
        it_changes = (self._path != new_path)
        self._path = new_path
        if it_changes:
            self.event_generate('<<PathChanged>>')
            self._guess_filetype()

    def _guess_filetype(self, junk: object = None) -> None:
        if self.path is None:
            filetype = filetypes.get_filetype_by_name(
                settings.get('default_filetype', str))
        else:
            # FIXME: this may read the shebang from the file, but the file
            #        might not be saved yet because save_as() sets self.path
            #        before saving, and that's when this runs
            filetype = filetypes.guess_filetype(self.path)

        self.filetype_to_settings(filetype)

    def filetype_to_settings(self, filetype: Dict[str, Any]) -> None:
        log.info(f"applying filetype settings: {filetype!r}")
        for name, value in filetype.items():
            # Ignore stuff used only for guessing the correct filetype
            if name not in {'filename_patterns', 'shebang_regex'}:
                self.settings.set(name, value, from_config=True)

    # TODO: plugin
    def _update_title(self, junk: object = None) -> None:
        text = 'New File' if self.path is None else self.path.name
        if not self.is_saved():
            # TODO: figure out how to make the label red in ttk instead
            #       of stupid stars
            text = '*' + text + '*'
        self.title = text

    def _update_status(self, junk: object = None) -> None:
        if self.path is None:
            path_string = "New file"
        else:
            path_string = "File '%s'" % self.path
        line, column = self.textwidget.index('insert').split('.')
        self.status = f"{path_string}\tLine {line}, column {column}"

    def can_be_closed(self) -> bool:    # override
        if self.is_saved():
            return True

        if self.path is None:
            msg = "Do you want to save your changes?"
        else:
            msg = f"Do you want to save your changes to {self.path.name}?"
        answer = messagebox.askyesnocancel("Close file", msg)
        if answer is None:
            # cancel
            return False
        if answer:
            # yes
            save_result = self.save()
            if save_result is None:
                # saving failed
                return False
            elif save_result:
                # saving succeeded
                return True
            else:
                # user said no
                return False
        # no was clicked, can be closed
        return True

    def on_focus(self) -> None:    # override
        self.textwidget.focus_set()

    # TODO: returning None on errors kinda sucks, maybe a handle_errors kwarg?
    def save(self) -> Optional[bool]:
        """Save the file to the current :attr:`path`.

        This calls :meth:`save_as` if :attr:`path` is None, and returns
        False if the user cancels the save as dialog. None is returned
        on errors, and True is returned in all other cases. In other
        words, this returns True if saving succeeded.

        .. seealso:: The :virtevt:`Save` event.
        """
        if self.path is None:
            return self.save_as()

        self.event_generate('<<Save>>')

        encoding = self.settings.get('encoding', str)
        try:
            with utils.backup_open(self.path, 'w', encoding=encoding) as f:
                f.write(self.textwidget.get('1.0', 'end - 1 char'))
        except (OSError, UnicodeError) as e:
            log.exception("saving '%s' failed", self.path)
            utils.errordialog(type(e).__name__, "Saving failed!",
                              traceback.format_exc())
            return None

        self.mark_saved()
        return True

    def save_as(self) -> bool:
        """Ask the user where to save the file and save it there.

        Returns True if the file was saved, and False if the user
        cancelled the dialog.
        """
        # type ignored because mypy **kwargs support isn't great
        path: str = filedialog.asksaveasfilename(    # type: ignore
            **filetypes.get_filedialog_kwargs())
        if not path:     # it may be '' because tkinter
            return False

        self.path = pathlib.Path(path)
        self.save()
        return True

    # FIXME: don't ignore undo history :/
    def get_state(self) -> _FileTabState:
        # e.g. "New File" tabs are saved even though the .path is None
        if self.is_saved() and self.path is not None:
            # this is really saved
            content = None
        else:
            content = self.textwidget.get('1.0', 'end - 1 char')

        return (self.path, content, self._save_hash,
                self.textwidget.index('insert'))

    @classmethod
    def from_state(cls: Type[_FileTabT], manager: TabManager, state: _FileTabState) -> _FileTabT:
        path, content, save_hash, cursor_pos = state
        if content is None:
            # nothing has changed since saving, read from the saved file
            assert path is not None
            assert isinstance(path, pathlib.Path)
            self = cls.open_file(manager, path)
        else:
            self = cls(manager, content, path)

        # the title depends on the saved hash
        self._save_hash = save_hash
        self._update_title()

        self.textwidget.mark_set('insert', cursor_pos)
        self.textwidget.see('insert linestart')
        return self
