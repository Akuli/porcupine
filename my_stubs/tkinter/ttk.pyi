import sys
import tkinter
import _tkinter
from typing import (
    Any,        # use this sparingly lol
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
    overload,
)

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


class Widget(tkinter.Widget): pass
class Frame(Widget): pass
class Separator(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        orient: Union[Literal['horizontal'], Literal['vertical']] = ...,
    ) -> None: ...

class Label(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        text: str = ...,
        image: tkinter.PhotoImage = ...,
        cursor: str = ...,
        font: tkinter._FontSpec = ...,
        width: int = ...,
        anchor: Literal['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw', 'center'] = ...,
    ) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['text'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['wraplength'], val: tkinter._ScreenDistance) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['image'], val: tkinter.PhotoImage) -> None: ...

class Checkbutton(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        text: str = ...,
        variable: tkinter.BooleanVar = ...,
    ) -> None: ...

class Button(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        text: str = ...,
        command: Callable[[], None] = ...,
        state: Literal['normal', 'disabled'] = ...,
    ) -> None: ...

    def __getitem__(self, opt: Literal['state', 'text']) -> Any: ...
    @overload
    def __setitem__(self, opt: Literal['state'], val: Literal['normal', 'disabled']) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['text'], val: str) -> None: ...

_NotebookTabId = Union[
    # see TAB IDENTIFIERS in ttk_notebook man page
    int,                # between 0 and number of tabs
    tkinter.Widget,     # turns into name of a slave window when tkinter str()s this
    str,                # "@x,y", "current" or "end"
]
_Compound = Union[
                        Literal['top'],
    Literal['left'],    Literal['center'],  Literal['right'],
                        Literal['bottom'],

    Literal['none'],
]

# Some Notebook methods are supposed to return Widgets, but they actually
# return strings that have to be passed to nametowidget. I'm also allowing it
# to return a widget in case this is "fixed" in a future version of tkinter.
#
# Currently nametowidget(tkinter widget) returns the widget as is, because it
# str()s the argument and that gives the widget's name. However, there's no
# comment about why it str()s the name, so I'm arfaid that someone "cleaning up"
# tkinter might break this later. I'm not trying to insult Python devs in
# particular, and most programmers just like to make mistakes and delete
# "unnecessary" code.
#
# I recommend doing this every time you call a method notebook.foo() that
# returns a _StringlyTypedWidget:
#
#    widget = notebook.nametowidget(str(notebook.foo()))
#    # do something with widget
#
# Do this with _OptionalStringlyTypedWidget:
#
#    possibly_string = notebook.foo()
#    if possibly_string:
#        widget = notebook.nametowidget(str(possibly_string))
#        # do something with widget
#    else:
#        # it's perhaps supposed to return None, but currently notebook.foo()
#        # is returning empty string when you get here

# currently always str
_StringlyTypedWidget = Union[str, tkinter.Widget]

# currently always str, and empty string for missing
_OptionalStringlyTypedWidget = Union[str, tkinter.Widget, None]


class Notebook(Widget):
    def add(
        self, child: tkinter.Widget, *,
        text: str = ...,
        compound: _Compound = ...,
        image: tkinter.PhotoImage = ...,
    ) -> None: ...

    def forget(self, tab_id: _NotebookTabId) -> None: ...
    def hide(self, tab_id: _NotebookTabId) -> None: ...

    # .identify() seems to be implicitly 'pathname identify element' in the
    # ttk_notebook man page. Tkinter calls it like in this Tcl session:
    #
    #    wish8.6 [~] .nb identify 10 10
    #    focus
    #
    # This seems to be same as 'identify element', but undocumented:
    #
    #    wish8.6 [~] .nb identify element 10 10
    #    focus
    #    wish8.6 [~] .nb identify tab 10 10
    #    0
    #
    # Return type is not Union of Literal because man page doesn't give a list
    # of possible return values for 'identify element'.
    def identify(self, x: int, y: int) -> str: ...

    def index(self, tab_id: _NotebookTabId) -> int: ...
    def insert(self, pos: Union[Literal['end'], int, tkinter.Widget], child: tkinter.Widget) -> None: ...

    @overload
    def select(self, tab_id: _NotebookTabId) -> Literal['']: ...
    @overload
    def select(self) -> _OptionalStringlyTypedWidget: ...

    # tab called with no kwargs returns current config as dict. Otherwise it
    # changes the config. There seems to be no way to type hint this correctly.
    #
    # TODO: if nothing else can be done, then at least avoid Any
    @overload
    def tab(
        self, tab_id: _NotebookTabId, option: None = ..., *,
        text: str = ...,
    ) -> Optional[Dict[str, Any]]: ...
    @overload
    def tab(self, tab_id: _NotebookTabId, option: Literal['text']) -> Any: ...

    def tabs(self) -> Tuple[_StringlyTypedWidget, ...]: ...


# from tkinter/ttk.py:
#
#   PanedWindow = Panedwindow # tkinter name compatibility
#
# I use Panedwindow directly instead of a possibly confusing alias, so there's
# no PanedWindow here.
class Panedwindow(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        orient: Union[Literal['horizontal'], Literal['vertical']] = ...,
    ) -> None: ...

    def add(self, child: Widget, *, weight: int = ...) -> None: ...

    @overload
    def sashpos(self, index: int) -> int: ...
    @overload
    def sashpos(self, index: int, newpos: int) -> int: ...

class Scrollbar(Widget):
    # There are many ways how the command may get called. Search for
    # 'SCROLLING COMMANDS' in scrollbar man page. There doesn't seem to be any
    # way to specify an overloaded callback function, so we say that it can
    # take any args while it can't in reality.
    def __setitem__(self, opt: Literal['command'], val: Callable[..., Optional[Tuple[float, float]]]) -> None: ...

    # first and last are strings when used as yscrollcommand command
    def set(self, first: Union[float, str], last: Union[float, str]) -> None: ...

_TreeviewShowMode = Union[Literal['tree'], Literal['headings']]

class Treeview(Widget, tkinter.YView):
    def __init__(
        self, master: tkinter.Misc, *,
        selectmode: Union[Literal['extended'], Literal['browse'], Literal['none']] = ...,
        show: Union[_TreeviewShowMode, List[_TreeviewShowMode]] = ...,
        columns: Tuple[str, ...] = ...,
    ) -> None: ...

    # TODO: belongs to YView but is currently copy/pasted to every subclasses
    def __setitem__(self, opt: Literal['yscrollcommand'], val: Union[str, Callable[[float, float], None]]) -> None: ...
    def __getitem__(self, opt: Literal['yscrollcommand']) -> str: ...

    def delete(self, *args: str) -> None: ...
    def get_children(self, item: str = ...) -> Tuple[str, ...]: ...

    # ttk_treeview(3tk) says that 'identify row' is "Obsolescent synonym
    # for pathname identify item", but tkinter doesn't have identify_item
    def identify_row(self, y: int) -> str: ...      # may return empty string

    def insert(
        self, parent: str, index: Union[int, Literal['end']], *,
        # tkinter supports both 'id' and 'iid' for the name of this arg. I like
        # 'id' because it's less confusing, even though it's also a built-in
        # function.
        id: str = ...,
        text: str = ...,
        values: Tuple[str, ...] = ...,
    ) -> str: ...

    # TODO: int vs ScreenUnits
    def column(self, column: int, *, width: int = ..., minwidth: int = ...) -> Optional[Dict[str, Any]]: ...
    def heading(self, column: int, *, text: str = ...) -> Optional[Dict[str, Any]]: ...
    @overload
    def item(self, item: str, option: Literal['values']) -> Any: ...
    @overload
    def item(self, item: str, *, values: Tuple[str, ...] = ...) -> Optional[Any]: ...

    # prev(first item) and next(last item) return empty string
    def prev(self, item: str) -> str: ...
    def next(self, item: str) -> str: ...

    def see(self, item: str) -> None: ...
    def selection(self) -> Tuple[str, ...]: ...
    def selection_set(self, items: Union[str, List[str], Tuple[str]]) -> None: ...

class Progressbar(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        mode: Union[Literal['determinate'], Literal['indeterminate']],
    ) -> None: ...
    def start(self, interval: int = ...) -> None: ...

# see INDICES in entry man page for possible string values
_EntryIndex = Union[str, int]

class Entry(Widget):
    def __init__(
        self, master: tkinter.Misc, *,
        textvariable: tkinter.StringVar = ...,
        font: tkinter._FontSpec = ...,
        width: int = ...,
        justify: Union[Literal['left'], Literal['center'], Literal['right']] = ...,
    ) -> None: ...
    def get(self) -> str: ...
    def insert(self, index: _EntryIndex, string: str) -> None: ...
    def selection_range(self, start: _EntryIndex, end: _EntryIndex) -> None: ...

    def __getitem__(self, opt: Literal['state']) -> Any: ...

    @overload
    def __setitem__(self, opt: Literal['validatecommand'], val: Callable[[], bool]) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['state'], val: Union[Literal['normal'], Literal['disabled'], Literal['readonly']]) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['textvariable'], val: tkinter.StringVar) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['validate'], val: Literal['none','key','focus','focusin','focusout','all']) -> None: ...

class Combobox(Entry):
    def __init__(
        self, master: tkinter.Misc, *,
        values: List[str],
        # rest is copy/pasta from Entry
        textvariable: tkinter.StringVar,
    ) -> None: ...
    def __getitem__(self, opt: Literal['state', 'values']) -> Any: ...

class Spinbox(Entry):
    def __init__(
        self, master: tkinter.Misc, *,
        from_: int,
        to: int,
        textvariable: tkinter.IntVar,   # differs from Entry
    ) -> None: ...
    def __getitem__(self, opt: Literal['from', 'to', 'state']) -> Any: ...

class Sizegrip(Widget): ...
