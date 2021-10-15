r"""Tabs as in browser tabs, not \t characters."""
from __future__ import annotations

import collections
import dataclasses
import hashlib
import importlib
import itertools
import logging
import os
import tkinter
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Iterable, NamedTuple, Optional, Sequence, Type, TypeVar

from pygments.lexer import LexerMeta
from pygments.lexers import TextLexer

from porcupine import _state, settings, textutils, utils

log = logging.getLogger(__name__)
_flatten = itertools.chain.from_iterable
_T = TypeVar("_T")


def _find_duplicates(items: list[_T], key: Callable[[_T], str]) -> Iterable[list[_T]]:
    items_by_key: dict[str, list[_T]] = {}
    for item in items:
        items_by_key.setdefault(key(item), []).append(item)
    return [itemlist for itemlist in items_by_key.values() if len(itemlist) >= 2]


def _short_ways_to_display_path(path: Path) -> list[str]:
    parts = str(path).split(os.sep)
    return [parts[-1], parts[-2] + os.sep + parts[-1]] + [
        first_part + os.sep + "..." + os.sep + parts[-1] for first_part in parts[:-2]
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

    .. virtualevent:: FileSystemChanged

        Runs when a file has been saved, a command finishes running, the
        Porcupine window is focused, or there's some other reason why files on
        the disk have likely changed.

        This event is in the tab manager and not in the main window (see
        :func:`porcupine.get_main_window`), because bindings of the main window
        also get notified for the events of all child widgets, and there is
        also a tab-specific :virtevt:`~Tab.FileSystemChanged` event.

    .. method:: add(child, **kw)
    .. method:: enable_traversal()
    .. method:: forget(tab_id)
    .. method:: hide(tab_id)
    .. method:: tab(tab_id, option=None, **kw)

        Don't use these methods. They are inherited from
        ``ttk.Notebook``, and :class:`TabManager` has other methods for
        doing what is usually done with these methods.

        .. seealso::
            :meth:`add_tab`, :meth:`close_tab`, :attr:`Tab.title`
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.bind("<<NotebookTabChanged>>", self._on_tab_selected, add=True)
        self.bind("<<FileSystemChanged>>", self._on_fs_changed, add=True)
        self.winfo_toplevel().bind("<FocusIn>", self._handle_main_window_focus, add=True)

        # the string is call stack for adding callback
        self._tab_callbacks: list[tuple[Callable[[Tab], Any], str]] = []

    def _handle_main_window_focus(self, event: tkinter.Event[tkinter.Misc]) -> None:
        if event.widget is self.winfo_toplevel():
            self.event_generate("<<FileSystemChanged>>")

    def _on_tab_selected(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        tab = self.select()
        if tab is not None:
            tab.event_generate("<<TabSelected>>")
            tab.event_generate("<<FileSystemChanged>>")

    def _on_fs_changed(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        tab = self.select()
        if tab is not None:
            tab.event_generate("<<FileSystemChanged>>")

    def _update_tab_titles(self) -> None:
        titlelists = [list(tab.title_choices) for tab in self.tabs()]
        while True:
            did_something = False
            for conflicting_title_lists in _find_duplicates(
                titlelists, key=(lambda lizt: lizt[0].strip("*"))
            ):
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
    def select(self, tab_id: Tab | int | None = None) -> Tab | None:
        """Select the given tab as if the user clicked it.

        Usually the ``tab_id`` should be a :class:`.Tab` widget. If it is not
        given, this returns the currently selected tab or None if there are no
        tabs.
        """
        if tab_id is None:
            selected = super().select()
            if not selected:  # no tabs, selected == ''
                return None
            return self.nametowidget(str(selected))

        # the tab can be e.g. an index, that's why two super() calls
        super().select(tab_id)
        return None

    def tabs(self) -> tuple[Tab, ...]:
        """Return a tuple of tabs in the tab manager.

        This returns a tuple instead of a list for compatibility with
        tkinter.
        """
        # tkinter has a bug that makes the original tabs() return widget name
        # strings instead of widget objects
        return tuple(self.nametowidget(tab) for tab in super().tabs())

    def open_file(self, path: Path) -> FileTab | None:
        """Add a :class:`FileTab` for editing a file and select it.

        If the file can't be opened, this method displays an error to the user
        and returns ``None``.
        """

        try:
            if path.stat().st_size > 1_000_000 and not messagebox.askyesno(
                "Open big file",
                "Uhh, this file is huge!\nAre you sure you want to open it? ",
                detail=(
                    "This file is larger than 1MB. If you open it, Porcupine may be unusably slow"
                    " or require an huge amount of RAM."
                ),
            ):
                return None
        except OSError:
            pass  # no problem, reload() will handle the error

        # Add tab before loading content, so that editorconfig plugin gets a
        # chance to set the encoding into tab.settings
        tab = FileTab(self, path=path)
        existing_tab = self.add_tab(tab)
        if existing_tab != tab:
            # tab is destroyed
            assert isinstance(existing_tab, FileTab)
            existing_tab.textwidget.focus()
            return existing_tab

        if not tab.reload(undoable=False):
            self.close_tab(tab)
            return None

        tab.textwidget.mark_set("insert", "1.0")
        return tab

    def add_tab(self, tab: Tab, select: bool = True) -> Tab:
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

        self.add(tab)
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

    def close_tab(self, tab: Tab) -> None:
        """Destroy a tab without calling :meth:`~Tab.can_be_closed`.

        The closed tab cannot be added back to the tab manager later.

        .. seealso:: The :meth:`.Tab.can_be_closed` method.
        """
        self.forget(tab)
        tab.destroy()
        self._update_tab_titles()

    def add_tab_callback(self, func: Callable[[Tab], Any]) -> None:
        """Run a callback for each tab in the tab manager.

        When new tabs are added later, the callback will be ran for them too.
        Bind to the ``<Destroy>`` event of each tab if you want to clean
        up something when a tab is closed.

        The return value of the callback is ignored.
        """
        for tab in self.tabs():
            func(tab)
        self._tab_callbacks.append((func, "".join(traceback.format_stack())))

    def add_filetab_callback(self, func: Callable[[FileTab], Any]) -> None:
        """
        Just like :meth:`add_tab_callback`, but the callback doesn't run if the
        tab is not a :class:`FileTab`.
        """

        def func_with_checking_for_filetab(tab: Tab) -> None:
            if isinstance(tab, FileTab):
                func(tab)

        self.add_tab_callback(func_with_checking_for_filetab)


_TabT = TypeVar("_TabT", bound="Tab")
_FileTabT = TypeVar("_FileTabT", bound="FileTab")


class Tab(ttk.Frame):
    """Base class for widgets that can be added to TabManager.

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

    .. virtualevent:: TabSelected

        :class:`TabManager` generates this event on the tab when the tab is
        selected. Unlike :virtevt:`~TabManager.NotebookTabSelected`, this event
        is bound on the tab and not the tab manager, and hence is automatically
        unbound when the tab is destroyed.

    .. virtualevent:: FileSystemChanged

        Just like the :virtevt:`~Tab.FileSystemChanged` event of
        :class:`TabManager`, except:

            * It is available on each tab, not on the tab manager.
            * It doesn't run when the tab isn't selected.
            * It runs for the newly selected tab when a tab is selected.

    .. attribute:: title_choices

        A :class:`typing.Sequence` of strings that can be used as the title of
        the tab, next to the red close button.

        Usually the first title of the list is used, but if multiple tabs have
        the same first title, then the second title is used instead, and so on.
        For example, if you open a file named ``foo/bar/baz.py``, its title
        will be ``baz.py``, but if you also open ``foo/bar2/baz.py`` then the
        titles change to ``bar/baz.py`` and ``bar2/baz.py``.

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
        self._titles: Sequence[str] = [""]

        # top and bottom frames must be packed first because this way
        # they extend past other frames in the corners
        self.top_frame = ttk.Frame(self)
        self.bottom_frame = ttk.Frame(self)
        self.left_frame = ttk.Frame(self)
        self.right_frame = ttk.Frame(self)
        self.top_frame.pack(side="top", fill="x")
        self.bottom_frame.pack(side="bottom", fill="x")
        self.left_frame.pack(side="left", fill="y")
        self.right_frame.pack(side="right", fill="y")

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

    def equivalent(self, other: Tab) -> bool:
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

    def get_state(self) -> Any | None:
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
    def from_state(cls: Type[_TabT], manager: TabManager, state: Any) -> _TabT | None:
        """Create a new tab from the return value of :meth:`get_state`.

        Be sure to override this if you override :meth:`get_state`.
        You can return ``None`` to indicate that the tab can't be loaded,
        but in that case, you should also let the user know about it.
        """
        raise NotImplementedError("from_state() wasn't overrided but get_state() was overrided")


class _FileTabState(NamedTuple):
    path: Path | None
    content: str | None
    saved_state: tuple[os.stat_result | None, int, str]
    cursor_pos: str
    settings_state: dict[str, Any]


def _import_lexer_class(name: str) -> LexerMeta:
    modulename, classname = name.rsplit(".", 1)
    module = importlib.import_module(modulename)
    klass = getattr(module, classname)
    if not isinstance(klass, LexerMeta):
        raise TypeError(f"expected a Lexer subclass, got {klass}")
    return klass


@dataclasses.dataclass
class ReloadInfo(utils.EventDataclass):
    had_unsaved_changes: bool


# Runs in O(n) time where n = max(old_content.count('\n'), new_content.count('\n'))
def _find_changed_part(old_content: str, new_content: str) -> tuple[str, str, str]:
    old_lines = collections.deque(old_content.splitlines(keepends=True))
    new_lines = collections.deque(new_content.splitlines(keepends=True))
    start_line = 1
    start_column = 0
    if old_lines and not old_lines[-1].endswith("\n"):
        # "foo\nbar" --> ["foo\n", "bar"] --> line 2, column 3
        end_line = len(old_lines)
        end_column = len(old_lines[-1])
    else:
        # "foo\nbar\n" --> ["foo\n", "bar\n"] --> line 3, column 0
        # "" --> [] --> line 1, column 0
        end_line = len(old_lines) + 1
        end_column = 0

    while old_lines and new_lines and old_lines[-1] == new_lines[-1]:
        popped = old_lines.pop()
        popped2 = new_lines.pop()
        assert popped == popped2
        if popped.endswith("\n"):
            assert end_column == 0
            end_line -= 1
        else:
            end_column = 0

    while old_lines and new_lines and old_lines[0] == new_lines[0]:
        old_lines.popleft()
        new_lines.popleft()
        start_line += 1

    return (f"{start_line}.{start_column}", f"{end_line}.{end_column}", "".join(new_lines))


class FileTab(Tab):
    """A subclass of :class:`.Tab` that represents an opened file.

    The filetab will have *content* in it by default when it's opened. If
    *path* is given, the file will be saved there when Ctrl+S (or ⌘S on Mac) is
    pressed. Otherwise this becomes a "New File" tab.

    If you want to open a new tab for editing an existing file,
    use :meth:`TabManager.open_file`.

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

            ``comment_prefix``: :class:`str`

            ``line_ending``: :class:`settings.LineEnding`

        See :source:`porcupine/default_filetypes.toml` for a description of
        each option.

    .. virtualevent:: TabSettingChanged:foo

        When the ``indent_size`` of :attr:`~settings` is set,
        the tab receives (but the child widgets of the tab don't receive)
        a virtual event named ``<<TabSettingChanged:indent_size>>``.
        This works similarly for other tab settings.

    .. virtualevent:: BeforeSave

        This runs before the file is saved with the :meth:`save` method.

    .. virtualevent:: AfterSave

        This runs after the file is saved with the :meth:`save` method.

    .. attribute:: textwidget
        :type: porcupine.textutils.MainText

        The central text widget of the tab.

        When a new :class:`FileTab` is created,
        :func:`porcupine.textutils.track_changes` is automatically called for
        the text widget.

    .. attribute:: panedwindow
        :type: porcupine.utils.PanedWindow

        This widget contains the :attr:`textwidget`.
        Its purpose is to allow plugins like :source:`minimap <porcupine/plugins/minimap.py>`
        to add other resizable widgets next to the :attr:`textwidget`.

    .. attribute:: scrollbar
        :type: tkinter.ttk.Scrollbar

        This is the scrollbar next to :attr:`.textwidget`.

        Things like :source:`the line number plugin <porcupine/plugins/linenumbers.py>` use this attribute.

    .. attribute:: path
        :type: pathlib.Path | None

        The path where this file is currently saved.

        This is None if the file has never been saved, and otherwise
        an absolute path.

        .. seealso:: The :virtevt:`PathChanged` virtual event.
    """

    def __init__(self, manager: TabManager, content: str = "", path: Path | None = None) -> None:
        super().__init__(manager)

        if path is None:
            self._path = None
        else:
            self._path = path.resolve()

        self.settings = settings.Settings(self, "<<TabSettingChanged:{}>>")
        self.settings.add_option(
            "pygments_lexer", TextLexer, LexerMeta, converter=_import_lexer_class
        )
        self.settings.add_option("tabs2spaces", True)
        self.settings.add_option("indent_size", 4)
        self.settings.add_option("encoding", "utf-8")
        self.settings.add_option("comment_prefix", None, Optional[str])
        self.settings.add_option(
            "line_ending",
            settings.get("default_line_ending", settings.LineEnding),
            converter=settings.LineEnding.__getitem__,
        )

        # I don't know why this needs a type annotation for self.panedwindow
        self.panedwindow: utils.PanedWindow = utils.PanedWindow(
            self, orient="horizontal", borderwidth=0
        )
        self.panedwindow.pack(side="left", fill="both", expand=True)

        # we need to set width and height to 1 to make sure it's never too
        # large for seeing other widgets
        #
        # I don't know why this needs a type annotation for self.textwidget
        self.textwidget: textutils.MainText = textutils.MainText(
            self, width=1, height=1, wrap="none", undo=True, padx=3
        )
        self.panedwindow.add(self.textwidget, stretch="always")

        if content:
            self.textwidget.insert("1.0", content)
            self.textwidget.edit_reset()  # can't undo initial insertion
        self._set_saved_state((None, self._get_char_count(), self._get_hash()))

        self.bind("<<TabSelected>>", (lambda event: self.textwidget.focus()), add=True)

        self.scrollbar = ttk.Scrollbar(self.right_frame)
        self.scrollbar.pack(side="right", fill="y")
        self.textwidget.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.textwidget.yview)

        self.textwidget.bind("<<ContentChanged>>", self._update_titles, add=True)
        self.bind("<<PathChanged>>", self._update_titles, add=True)
        self.bind("<<TabSettingChanged:encoding>>", self._update_titles, add=True)
        self.bind("<<TabSettingChanged:line_ending>>", self._update_titles, add=True)
        self.bind(
            "<<AfterSave>>", (lambda e: manager.event_generate("<<FileSystemChanged>>")), add=True
        )
        self._update_titles()

        self._previous_reload_failed = False

    def _get_char_count(self) -> int:
        return textutils.count(self.textwidget, "1.0", "end - 1 char")

    def _get_hash(self, content: bytes | None = None) -> str:
        if content is None:
            # This is not the right place to handle encoding errors. If it
            # contains characters that the encoding doesn't support, it should
            # error when user tries to save the file, not when this method gets
            # called for some unintuitive reason.
            newline = self.settings.get("line_ending", settings.LineEnding).value.encode("ascii")
            content = (
                self.textwidget.get("1.0", "end - 1 char")
                .encode(self.settings.get("encoding", str), errors="replace")
                .replace(b"\n", newline)
            )
        return hashlib.md5(content).hexdigest()

    def _set_saved_state(self, state: tuple[os.stat_result | None, int, str]) -> None:
        self._saved_state = state
        self._update_titles()

    def has_unsaved_changes(self) -> bool:
        """Return True if the text in the editor has changed since the previous save."""
        stat_result, char_count, save_hash = self._saved_state
        # Don't call _get_hash() if not necessary
        return self._get_char_count() != char_count or self._get_hash() != save_hash

    def reload(self, *, undoable: bool = True) -> bool:
        """Read the contents of the file from disk.

        This method returns ``True`` on success, and if reading the file fails, the error
        is shown to the user and ``False`` is returned.

        If ``undoable=False`` is given, the reload cannot be undone with Ctrl+Z.

        .. seealso:: :meth:`TabManager.open_file`, :meth:`other_program_changed_file`
        """
        assert self.path is not None

        # Disable text widget so user can't type into it during load
        assert self.textwidget["state"] == "normal"
        self.textwidget.config(state="disabled")

        while True:
            try:
                with self.path.open("r", encoding=self.settings.get("encoding", str)) as f:
                    stat_result = os.fstat(f.fileno())
                    content = f.read()
                break

            except OSError as e:
                if self._previous_reload_failed:
                    # Do not spam user with errors (not terminal either)
                    log.info(f"opening '{self.path}' failed", exc_info=True)
                else:
                    log.exception(f"opening '{self.path}' failed")
                    wanna_retry = messagebox.askretrycancel(
                        "Opening failed",
                        f"{type(e).__name__}: {e}",
                        detail="Make sure that the file exists and try again.",
                    )
                    if wanna_retry:
                        continue

            except UnicodeDecodeError:
                bad_encoding = self.settings.get("encoding", str)
                user_selected_encoding = utils.ask_encoding(
                    f'The content of "{self.path}" is not valid {bad_encoding}. Choose an encoding'
                    " to use instead:",
                    bad_encoding,
                )
                if user_selected_encoding is not None:
                    self.settings.set("encoding", user_selected_encoding)
                    continue  # try again

            # Error message shown if needed, let user continue editing
            self.textwidget.config(state="normal")
            self._previous_reload_failed = True
            self._set_saved_state((None, -1, "dummy hash"))  # Do not consider file saved
            return False

        if isinstance(f.newlines, tuple):
            # TODO: show a message box to user?
            log.warning(f"file '{self.path}' contains mixed line endings: {f.newlines}")
        elif f.newlines is not None:
            assert isinstance(f.newlines, str)
            self.settings.set("line_ending", settings.LineEnding(f.newlines))

        was_unsaved = self.has_unsaved_changes()

        start, end, changed_part_content = _find_changed_part(
            self.textwidget.get("1.0", "end - 1 char"), content
        )
        self.textwidget.config(state="normal")
        with textutils.change_batch(self.textwidget):
            self.textwidget.replace(start, end, changed_part_content)

        if not undoable:
            self.textwidget.edit_reset()

        self._set_saved_state((stat_result, self._get_char_count(), self._get_hash()))

        # TODO: document this
        self.event_generate("<<Reloaded>>", data=ReloadInfo(had_unsaved_changes=was_unsaved))
        self._previous_reload_failed = False
        return True

    def other_program_changed_file(self) -> bool:
        """Check whether some other program has changed the file.

        Programs like ``git`` often change the file while it's open in an
        editor. After they do that, this method will return True until the file
        is e.g. saved or reloaded.
        """
        save_stat, save_char_count, save_hash = self._saved_state
        if self.path is None or save_stat is None:
            return False

        try:
            # We could just reading the contents of the file, but it can often be avoided.
            actual_stat = self.path.stat()
            if actual_stat.st_mtime == save_stat.st_mtime:
                log.debug(f"{self.path}: modified time has not changed")
                return False
            if actual_stat.st_size != save_stat.st_size:
                log.debug(f"{self.path}: size has changed")
                return True

            log.info(f"reading {self.path} to figure out if reload is needed")
            with self.path.open("rb") as f:
                actual_hash = self._get_hash(f.read())
            if actual_hash != save_hash:
                return True

            # Avoid reading file contents again soon
            self._set_saved_state((actual_stat, save_char_count, save_hash))
            return False

        except OSError:
            # File unreadable, already errors elsewhere, do not spam console with warning
            log.info(
                f"error when figuring out if '{self.path}' needs reloading, assuming it does",
                exc_info=True,
            )

            # Why return True on error:
            #   - Other program did change something, by making it unreadable
            #   - Indicates that something isn't saved
            return True

    def equivalent(self, other: Tab) -> bool:  # override
        # this used to have hasattr(other, "path") instead of isinstance
        # but it not work if a plugin defines custom tab with path attribute
        return (
            isinstance(other, FileTab)
            and self.path is not None
            and other.path is not None
            and self.path == other.path  # works even if files don't exist
        )

    @property
    def path(self) -> Path | None:
        return self._path

    @path.setter
    def path(self, new_path: Path | None) -> None:
        if new_path is not None:
            new_path = new_path.resolve()

        it_changes = self._path != new_path
        self._path = new_path
        if it_changes:
            self.event_generate("<<PathChanged>>")

    # TODO: plugin
    def _update_titles(self, junk: object = None) -> None:
        if self.path is None:
            titles = ["New File"]
        else:
            titles = _short_ways_to_display_path(self.path)

        if self.has_unsaved_changes():
            titles = [f"*{title}*" for title in titles]

        self.title_choices = titles

    def can_be_closed(self) -> bool:  # override
        if not self.has_unsaved_changes():
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
            return self.save()
        # no was clicked, can be closed
        return True

    def _do_the_save(self, path: Path) -> bool:
        self.event_generate("<<BeforeSave>>")

        while True:
            encoding = self.settings.get("encoding", str)
            line_ending = self.settings.get("line_ending", settings.LineEnding)

            try:
                with utils.backup_open(
                    path, "w", encoding=encoding, newline=line_ending.value
                ) as f:
                    f.write(self.textwidget.get("1.0", "end - 1 char"))
                    f.flush()  # needed to get right file size in stat
                    self._set_saved_state(
                        (os.fstat(f.fileno()), self._get_char_count(), self._get_hash())
                    )
                break

            except UnicodeEncodeError as e:
                bad_character = e.object[e.start : e.start + 1]
                log.info(
                    f"save to '{path}' failed, non-{encoding} character '{bad_character}'",
                    exc_info=True,
                )

                user_wants_utf8 = messagebox.askyesno(
                    "Saving failed",
                    f"'{bad_character}' is not a valid character in the {encoding} encoding. Do"
                    f" you want to save the file as UTF-8 instead of {encoding}?",
                )
                if user_wants_utf8:
                    self.settings.set("encoding", "utf-8")
                    continue

            except OSError as e:
                log.exception(f"saving to '{path}' failed")
                messagebox.showerror(
                    "Saving failed",
                    f"{type(e).__name__}: {e}",
                    detail="Make sure that the file is writable and try again.",
                )

            # If we get here, error message was shown
            return False

        self._save_hash = self._get_hash()
        self.path = path
        self.event_generate("<<AfterSave>>")
        return True

    def save(self) -> bool:
        """Save the file to the current :attr:`path`.

        This returns whether the file was actually saved. This means that
        ``False`` is returned when the user cancels a :meth:`save_as` dialog
        (can happen when :attr:`path` is None) or an error occurs (the error is
        logged).

        If the saving would overwrite changes done by other programs than
        Porcupine, then before saving, this function will ask whether the user
        really wants to save.

        .. seealso:: The :virtevt:`BeforeSave` and :virtevt:`AfterSave` virtual events.
        """
        if self.path is None:
            return self.save_as()

        if self.other_program_changed_file() and not self._previous_reload_failed:
            user_is_sure = messagebox.askyesno(
                "File changed",
                f"Another program has changed {self.path.name}. Are you sure you want to save it?",
            )
            if not user_is_sure:
                return False

        return self._do_the_save(self.path)

    def save_as(self, path: Path | None = None) -> bool:
        """Ask the user where to save the file and save it there.

        Returns True if the file was saved, and False if the user
        cancelled the dialog. If a ``path`` is given, it's used instead of
        asking the user.
        """
        if path is None:
            path_string = filedialog.asksaveasfilename(**_state.filedialog_kwargs)
            if not path_string:  # it may be '' because tkinter
                return False
            path = Path(path_string)

        # see equivalent()
        if any(
            isinstance(other, FileTab) and other.path == path
            for other in self.master.tabs()
            if other is not self
        ):
            messagebox.showerror(
                "Save As",
                f"{path.name!r} is already opened. "
                "Please close it before overwriting it with another file.",
                parent=self.winfo_toplevel(),
            )
            return False

        return self._do_the_save(path)

    # FIXME: don't ignore undo history :/
    # FIXME: when called from reload plugin, require saving file first
    def get_state(self) -> _FileTabState:
        # e.g. "New File" tabs are saved even though the .path is None
        if (
            self.path is not None
            and not self.has_unsaved_changes()
            and not self.other_program_changed_file()
        ):
            # this is really saved
            content = None
        else:
            content = self.textwidget.get("1.0", "end - 1 char")

        return _FileTabState(
            self.path,
            content,
            self._saved_state,
            self.textwidget.index("insert"),
            self.settings.get_state(),
        )

    @classmethod
    def from_state(
        cls: Type[_FileTabT], manager: TabManager, state: _FileTabState
    ) -> _FileTabT | None:
        assert isinstance(state, _FileTabState)  # not namedtuple in older porcupines

        tab = cls(manager, content=(state.content or ""), path=state.path)
        tab.settings.set_state(state.settings_state)  # must be before reload()
        if state.content is None:
            # no unsaved changes, read from the saved file
            if not tab.reload(undoable=False):
                tab.destroy()
                return None

        tab._set_saved_state(state.saved_state)  # TODO: does this make any sense?
        tab.textwidget.mark_set("insert", state.cursor_pos)
        tab.textwidget.see("insert linestart")
        return tab
