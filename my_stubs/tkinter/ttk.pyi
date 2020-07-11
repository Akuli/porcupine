import tkinter
from typing import (
    Any,        # use this sparingly lol
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    overload,
)


class Widget(tkinter.Widget): pass
class Frame(Widget): pass
class Separator(Widget): pass

class Label(Widget):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        text: str = ...,
    ) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['text'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['wraplength'], val: tkinter._ScreenDistance) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['image'], val: tkinter.PhotoImage) -> None: ...

class Checkbutton(Widget):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        text: str = ...,
        variable: tkinter.BooleanVar = ...,
    ) -> None: ...

class Button(Widget):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        text: str = ...,
        command: Callable[[], None] = ...,
    ) -> None: ...

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
    def insert(self, pos: Union[Literal['end'], int, tkinter.Widget], child: tkinter.Widget): ...

    @overload
    def select(self, tab_id: _NotebookTabId) -> Literal['']: ...
    @overload
    def select(self) -> _OptionalStringlyTypedWidget: ...

    # tab called with no kwargs returns current config as dict. Otherwise it
    # changes the config. There seems to be no way to type hint this correctly.
    #
    # TODO: if nothing else can be done, then at least avoid Any
    def tab(
        self, tab_id: _NotebookTabId, *,
        text: str = ...,
    ) -> Optional[Dict[str, Any]]: ...

    def tabs(self) -> Tuple[_StringlyTypedWidget, ...]: ...


# from tkinter/ttk.py:
#
#   PanedWindow = Panedwindow # tkinter name compatibility
#
# I use Panedwindow directly instead of a possibly confusing alias, so there's
# no PanedWindow here.
class Panedwindow(Widget): pass

class Scrollbar(Widget):
    # There are many ways how the command may get called. Search for
    # 'SCROLLING COMMANDS' in scrollbar man page. There doesn't seem to be any
    # way to specify an overloaded callback function, so we say that it can
    # take any args while it can't in reality.
    def __setitem__(self, opt: Literal['command'], val: Callable[..., Optional[Tuple[float, float]]]) -> None: ...

    def set(self, first: float, last: float) -> None: ...

class Entry(Widget):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        textvariable: tkinter.StringVar,
    ) -> None: ...

class Combobox(Entry):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        values: List[str],
        # rest is copy/pasta from Entry
        textvariable: tkinter.StringVar,
    ) -> None: ...

class Spinbox(Entry):
    def __init__(
        self, master: tkinter.BaseWidget, *,
        from_: int,
        to: int,
        textvariable: tkinter.IntVar,   # differs from Entry
    ) -> None: ...
