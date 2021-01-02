r"""Tabs as in browser tabs, not \t characters."""

import functools
import hashlib
import importlib
import itertools
import logging
import os
import pathlib
import tkinter
import traceback
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Type, TypeVar, Union, cast

from pygments.lexer import LexerMeta  # type: ignore[import]
from pygments.lexers import TextLexer  # type: ignore[import]

from porcupine import _state, images, settings, textwidget, utils

log = logging.getLogger(__name__)
_flatten = itertools.chain.from_iterable
_T = TypeVar('_T')


def _find_duplicates(items: List[_T], key: Callable[[_T], str]) -> Iterable[List[_T]]:
    for key_return_value, similar_items_iter in itertools.groupby(items, key=key):
        similar_items = list(similar_items_iter)
        if len(similar_items) >= 2:
            yield similar_items


def _short_ways_to_display_path(path: pathlib.Path) -> List[str]:
    parts = str(path).split(os.sep)
    return [parts[-1], parts[-2] + os.sep + parts[-1]] + [
        first_part + os.sep + '...' + os.sep + parts[-1]
        for first_part in parts[:-2]
    ]


class TabManager(ttk.Notebook):
    """A simple but awesome tab widget.

    This widget inherits from ``ttk.Notebook``. All widgets added to
    this should be :class:`Tab` objects.

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
        # creates. Undocumented because plugins shouldn't need this.
        self.bindings: List[Tuple[str, Callable[['tkinter.Event[tkinter.Misc]'], utils.BreakOrNone]]] = [
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

        # the string is call stack for adding callback
        self._tab_callbacks: List[Tuple[Callable[[Tab], Any], str]] = []

    def _focus_selected_tab(self, event: 'tkinter.Event[tkinter.Misc]') -> None:
        tab = self.select()
        if tab is not None:
            tab.on_focus()

    def _on_click(self, event: 'tkinter.Event[tkinter.Misc]') -> None:
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
            event: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
        if shifted:
            self.move_selected_tab(diff)
        else:
            self.select_another_tab(diff)
        return 'break'

    def _on_alt_n(self, n: int, event: 'tkinter.Event[tkinter.Misc]') -> utils.BreakOrNone:
        try:
            self.select(n - 1)
            return 'break'
        except tkinter.TclError:        # index out of bounds
            return None

    def _update_tab_titles(self) -> None:
        titlelists = [list(tab.title_choices) for tab in self.tabs()]
        while True:
            did_something = False
            for conflicting_title_lists in _find_duplicates(titlelists, key=(lambda lizt: lizt[0].strip("*"))):
                # shorten longest title lists
                maxlen = max(len(titlelist) for titlelist in conflicting_title_lists)
                if maxlen >= 2:
                    for titlelist in conflicting_title_lists:
                        if len(titlelist) == maxlen:
                            del titlelist[0]
                            did_something = True
            if not did_something:
                break

        for tab, titlelist in zip(self.tabs(), titlelists):
            self.tab(tab, text=titlelist[0])

    # fixing tkinter weirdness: some methods returns widget names as
    # strings instead of widget objects, these str() everything anyway
    # because tkinter might be fixed some day
    def select(self, tab_id: Union[None, int, 'Tab'] = None) -> Optional['Tab']:
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
        existing tab is returned and the tab passed in as an argument is
        destroyed. Otherwise *tab* is added to the tab manager and returned.

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
                tab.destroy()
                return existing_tab

        self.add(tab, image=images.get('closebutton'), compound='right')
        self._update_tab_titles()
        if select:
            self.select(tab)

        # The update() is needed in some cases because virtual events don't run
        # if the widget isn't visible yet.
        self.update()
        for callback, add_stack in self._tab_callbacks:
            try:
                callback(tab)
            except Exception:
                log.error("tab callback failed", exc_info=True)
                log.error(f"the callback was added here\n{add_stack}")
        return tab

    def close_tab(self, tab: 'Tab') -> None:
        """Destroy a tab without calling :meth:`~Tab.can_be_closed`.

        The closed tab cannot be added back to the tab manager later.

        .. seealso:: The :meth:`.Tab.can_be_closed` method.
        """
        self.forget(tab)
        tab.destroy()
        self._update_tab_titles()

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

    # TODO: write tests for this? otoh it's a feature that I use all the time
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

        self.forget(i2)
        self.insert(i1, tab, **options)
        if selected:
            self.select(tab)

        return True

    def add_tab_callback(self, func: Callable[['Tab'], Any]) -> None:
        """Run a callback for each tab in the tab manager.

        When new tabs are added later, the callback will be ran for them too.
        Bind to the ``<Destroy>`` event of each tab if you want to clean
        up something when a tab is closed.

        The return value of the callback is ignored.
        """
        for tab in self.tabs():
            func(tab)
        self._tab_callbacks.append((func, ''.join(traceback.format_stack())))


# _FileTabT represents a subclass of FileTab. Don't know if there's a better
# way to tell that to mypy than passing FileTab twice...
_TabT = TypeVar('_TabT', 'Tab', 'Tab')
_FileTabT = TypeVar('_FileTabT', 'FileTab', 'FileTab')


class Tab(ttk.Frame):
    r"""Base class for widgets that can be added to TabManager.

    You can easily create custom kinds of tabs by inheriting from this
    class. Here's a very minimal but complete example plugin::

        from tkinter import ttk
        from porcupine import get_tab_manager, menubar, tabs

        class HelloTab(tabs.Tab):
            def __init__(self, manager):
                super().__init__(manager)
                self.title_choices = ["Hello"]
                ttk.Label(self, text="Hello World!").pack()

        def new_hello_tab():
            get_tab_manager().add_tab(HelloTab(get_tab_manager()))

        def setup():
            menubar.get_menu("Hello").add_command(label="New Hello Tab", command=new_hello_tab)

    Note that you need to use the pack geometry manager when creating
    custom tabs. If you want to use grid or place you can create a frame
    inside the tab, pack it with ``fill='both', expand=True`` and do
    whatever you want inside it.

    .. virtualevent:: StatusChanged

        This event is generated when :attr:`status` is set to a new
        value. Use ``event.widget.status`` to access the current status.

    .. attribute:: title_choices

        A :class:`typing.Sequence` of strings that can be used as the title of
        the tab, next to the red close button.

        Usually the first title of the list is used, but if multiple tabs have
        the same first title, then the second title is used instead, and so on.
        For example, if you open a file named ``foo/bar/baz.py``, its title
        will be ``baz.py``, but if you also open ``foo/bar2/baz.py`` then the
        titles change to ``bar/baz.py`` and ``bar2/baz.py``.

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
        self._titles: Sequence[str] = ['']

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
    def title_choices(self) -> Sequence[str]:
        return self._titles

    @title_choices.setter
    def title_choices(self, titles: Sequence[str]) -> None:
        assert titles
        self._titles = titles
        if self in self.master.tabs():
            self.master._update_tab_titles()

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

        .. note::
            Make sure that your tab can't be changed so that it becomes
            equivalent with another tab that is already in the tab manager.
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


def _import_lexer_class(name: str) -> LexerMeta:
    modulename, classname = name.rsplit('.', 1)
    module = importlib.import_module(modulename)
    klass = getattr(module, classname)
    if not isinstance(klass, LexerMeta):
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

        This setting object is for file-specific settings,
        such as those loaded by :source:`porcupine/plugins/filetypes.py`.
        It contains the following settings by default (but plugins add more
        settings with :meth:`~porcupine.settings.Settings.add_option`):

            ``pygments_lexer``: a subclass of :class:`pygments.lexer.Lexer`

            ``tabs2spaces``: :class:`bool`

            ``indent_size``: :class:`int`

            ``encoding``: :class:`str`

            ``line_ending``: :class:`settings.LineEnding`

        See :source:`porcupine/default_filetypes.toml` for a description of
        each option.

    .. virtualevent:: TabSettingChanged:foo

        When the ``indent_size`` of :attr:`~settings` is set,
        the tab receives (but the child widgets of the tab don't receive)
        a virtual event named ``<<TabSettingChanged:indent_size>>``.
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
            self._path = path.resolve()

        self.settings = settings.Settings(self, '<<TabSettingChanged:{}>>')
        self.settings.add_option(
            'pygments_lexer', TextLexer, type=LexerMeta,
            converter=_import_lexer_class)
        self.settings.add_option('tabs2spaces', True)
        self.settings.add_option('indent_size', 4)
        self.settings.add_option('encoding', 'utf-8')
        self.settings.add_option(
            'line_ending', settings.get('default_line_ending', settings.LineEnding),
            converter=settings.LineEnding.__getitem__)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        self.textwidget = textwidget.MainText(
            self, width=1, height=1, wrap='none', undo=True)
        self.textwidget.pack(side='left', fill='both', expand=True)
        self.textwidget.bind('<<ContentChanged>>', self._update_titles,
                             add=True)

        if content:
            self.textwidget.insert('1.0', content)
            self.textwidget.edit_reset()   # reset undo/redo

        self.bind('<<PathChanged>>', self._update_status, add=True)
        self.textwidget.bind('<<CursorMoved>>', self._update_status, add=True)

        self.scrollbar = ttk.Scrollbar(self.right_frame)
        self.scrollbar.pack(side='right', fill='y')
        self.textwidget.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.textwidget.yview)

        self.mark_saved()
        self._update_titles()
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
        with path.open('r', encoding=tab.settings.get('encoding', str)) as file:
            content = file.read()
        tab.textwidget.insert('1.0', content)
        tab.textwidget.edit_reset()

        if isinstance(file.newlines, tuple):
            # TODO: show a message box to user?
            log.warning(f"file '{path}' contains mixed line endings: {file.newlines}")
        elif file.newlines is not None:
            assert isinstance(file.newlines, str)
            tab.settings.set('line_ending', settings.LineEnding(file.newlines))

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
        self._update_titles()

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
        if new_path is not None:
            new_path = new_path.resolve()

        it_changes = (self._path != new_path)
        self._path = new_path
        if it_changes:
            # filetype guessing must happen before <<PathChanged>> so that
            # plugins can override guessed stuff
            self.event_generate('<<PathChanged>>')

    # TODO: plugin
    def _update_titles(self, junk: object = None) -> None:
        if self.path is None:
            titles = ['New File']
        else:
            titles = _short_ways_to_display_path(self.path)

        if not self.is_saved():
            titles = [f'*{title}*' for title in titles]

        self.title_choices = titles

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
        line_ending = self.settings.get('line_ending', settings.LineEnding)

        try:
            with utils.backup_open(self.path, 'w', encoding=encoding, newline=line_ending.value) as f:
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
        path_string: str = filedialog.asksaveasfilename(**_state.filedialog_kwargs)
        if not path_string:     # it may be '' because tkinter
            return False
        path = pathlib.Path(path_string)

        # see equivalent()
        if any(isinstance(other, FileTab) and other.path == path
               for other in self.master.tabs()
               if other is not self):
            messagebox.showerror(
                "Save As",
                f"{path.name!r} is already opened. "
                "Please close it before overwriting it with another file.",
                parent=self.winfo_toplevel())
            return False

        self.path = path
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
            assert isinstance(path, pathlib.Path)  # older porcupines used strings
            self = cls.open_file(manager, path)
        else:
            self = cls(manager, content, path)

        # the title depends on the saved hash
        self._save_hash = save_hash
        self._update_titles()

        self.textwidget.mark_set('insert', cursor_pos)
        self.textwidget.see('insert linestart')
        return self
