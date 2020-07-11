import pathlib
from typing import (
    Any,        # use this sparingly lol
    Callable,
    Literal,
    List,
    Optional,
    Tuple,
    Union,
    overload,
)

# yes, this is a float
TkVersion: float = ...

class TclError(Exception): ...

# Tk uses the string '??' for missing things, and tkinter does it too
class Event:
    x: int
    y: int
    x_root: int
    y_root: int
    width: Union[int, Literal['??']]
    height: Union[int, Literal['??']]
    widget: 'BaseWidget'
    num: Union[int, Literal['??']]
    delta: int
    keysym: str     # can be '??'

_BindCallback = Callable[['Event'], Optional[Literal['break']]]

# see Tk_GetAnchor man page
_Anchor = Union[
    Literal['nw'],      Literal['n'],       Literal['ne'],
    Literal['w'],       Literal['center'],  Literal['e'],
    Literal['sw'],      Literal['s'],       Literal['se'],
]

# see Tk_GetRelief man page
_Relief = Union[
    Literal['flat'],
    Literal['raised'],
    Literal['sunken'],
    Literal['groove'],
    Literal['solid'],
    Literal['ridge'],
]

# string must be e.g. '12.34', '12.34c', '12.34i', '12.34m', '12.34p'
# see Tk_GetPixels man page for what each suffix means
#
# this is also used in ttk.pyi
_ScreenDistance = Union[str, int, float]

_PackSide = Union[Literal['left'], Literal['right'], Literal['top'], Literal['bottom']]
_PackFill = Union[Literal['none'], Literal['x'], Literal['y'], Literal['both']]
_PackPad = Union[
    Tuple[_ScreenDistance, _ScreenDistance],    # (top, bottom) or (left, right)
    _ScreenDistance,                    # same value used for both
]

# there are several ways to specify a font, see font(3tk) man page
_BoldOrStuff = Union[Literal['bold'], Literal['italic']]
_FontSpec = Union[
    # see font(3tk) man page for what this could be
    str,

    # ('Helvetica', 16, 'bold')
    # ('Helvetica', 16, ('bold', 'italic'))
    # ('Helvetica', 16, ['bold', 'italic'])
    # ('Helvetica', 16, [])
    Tuple[str, int, _BoldOrStuff],
    Tuple[str, int, Tuple[_BoldOrStuff, ...]],
    Tuple[str, int, List[_BoldOrStuff]],
]

# Tkinter makes widgets behave like dicts for options, as in
#
#   some_label['text'] = "Hello"
#   some_label['font'] = ('Helvetica', 12, 'bold')
#
# This is just like TypedDict, but making widgets inherit from TypedDict
# doesn't work. Instead we need a highly overloaded __getitem__.
#
# This is also used for anything else that uses options similarly, such as
# the PhotoImage class.
#
# The same options can be used as init kwargs. It has currently been 2 years
# since someone requested support for typing kwargs sanely, and it's still not
# implemented: https://github.com/python/mypy/issues/4441
#
# This means that we need to copy/pasta all __getitem__ overloads to __init__.
# And we also need to copy/paste all used __init__ args to subclasses:
# https://github.com/python/mypy/issues/8769
class PhotoImage:
    def __init__(
        self, *,
        file: pathlib.Path = ...,
        width: int = ...,
        height: int = ...,
    ) -> None: ...
    def width(self) -> int: ...
    def height(self) -> int: ...


class _TclInterpreter:
    # TODO: can't get eval to return non-string, does it always return string?
    #
    #    >>> t.tk.call('set', 'foo', (1, 2, 3))
    #    (1, 2, 3)
    #    >>> t.tk.eval('return $foo')
    #    '1 2 3'
    def call(self, command: str, *args: Any) -> Any: ...
    def eval(self, command: str) -> Any: ...


# Widget possibly without pack, grid, place. Use this if you want to specify
# any widget, including Toplevel and Tk, and use Widget if you want to specify
# a child widget.
class BaseWidget:
    # many of these methods are actually in Misc, but there's never need to
    # access them without some subclass of BaseWidget

    master: Optional['BaseWidget']

    # I don't think this is documented, but MANY sources online use this
    # occationally
    tk: _TclInterpreter

    # TODO: passing arguments to after callbacks
    def after(self, ms: int, func: Callable[[], None]) -> str: ...
    def after_idle(self, func: Callable[[], None]) -> str: ...
    def after_cancel(self, id: str) -> None: ...

    # add new binding
    @overload
    def bind(self, sequence: str, func: _BindCallback, add: bool = ...) -> str: ...

    # get all tcl code bound to sequence
    @overload
    def bind(self, sequence: str) -> str: ...

    # set the tcl code bound to sequence
    @overload
    def bind(self, sequence: str, func: str) -> None: ...

    def bind_all(self, sequence: str, func: _BindCallback, add: bool = ...) -> str: ...
    def deletecommand(self, name: str) -> None: ...
    def destroy(self) -> None: ...

    # The data is str()ed, and it can be anything that has valid str(). Note
    # that str(some_widget) returns the widget's Tcl command name, which can be
    # e.g. passed to nametowidget.
    def event_generate(self, sequence: str, *, x: int = ..., y: int = ..., data: Union[str, int, float, BaseWidget] = ...): ...

    def nametowidget(self, name: str) -> 'BaseWidget': ...

    # register() callbacks can do pretty much anything, can't do more specific type hints
    def register(self, func: Callable[..., Any]) -> str: ...

    def update(self) -> None: ...
    def wait_window(self) -> None: ...
    def winfo_children(self) -> List['BaseWidget']: ...
    def winfo_rgb(self, color: str) -> Tuple[int, int, int]: ...
    def winfo_rootx(self) -> int: ...
    def winfo_rooty(self) -> int: ...

# this class represents a widget that can be put inside another widget
class Widget(BaseWidget):

    # Toplevel and Tk are BaseWidgets but not Widgets. They also have master
    # but it's often None and not so useful. This is never None as far as I
    # know.
    master: BaseWidget

    # these methods are actually in 3 separate classes: Pack, Grid, Place,
    # but there should never be any need to use those directly so why bother
    # with them here
    def __init__(self, master: BaseWidget) -> None: ...
    def pack(
        self, *,
        side: _PackSide = ...,
        fill: _PackFill = ...,
        anchor: _Anchor = ...,
        expand: bool = ...,
        padx: _ScreenDistance = ...,
        pady: _ScreenDistance = ...) -> None: ...

# TODO: what other protocol names are there?
#       are some of these deprecated or supported only on some platforms?
_WmProtocolName = Union[
    Literal['WM_DELETE_WINDOW'],
    Literal['WM_SAVE_YOURSELF'],
    Literal['WM_TAKE_FOCUS'],
]

# stuff for Toplevel and Tk
class Wm:
    @overload
    def geometry(self) -> str: ...
    @overload
    def geometry(self, newGeometry: str) -> Literal['']: ...

    def overrideredirect(self, boolean: bool) -> None: ...
    def protocol(self, name: _WmProtocolName, func: Callable[[], None]) -> Literal['']: ...
    def title(self, string: str) -> Literal['']: ...
    def transient(self, master: Wm) -> Literal['']: ...
    def withdraw(self) -> Literal['']: ...
    def deiconify(self) -> Literal['']: ...

class Toplevel(BaseWidget, Wm): pass
class Tk(BaseWidget, Wm):

    # actually many widgets have this, but invoking it elsewhere doesn't make
    # much sense
    def mainloop(self) -> None: ...

class Label(Widget):
    def __init__(
        self, master: BaseWidget, *,
        text: str = ...,
        border: int = ...,
        fg: str = ...,
        bg: str = ...) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['text'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['wraplength'], val: _ScreenDistance) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['font'], val: _FontSpec) -> None: ...

_WrapMode = Union[Literal['none'], Literal['char'], Literal['word']]
_TextWidgetState = Union[Literal['normal'], Literal['disabled']]
_TagList = Union[str, List[str], Tuple[str]]
_CompareOp = Union[
    Literal['<'], Literal['>'],
    Literal['<='], Literal['>='],
    Literal['=='], Literal['!='],
]

# Text.tag_ranges() returns Tcl_Objs that can be str()ed or passed to tkinter
# wanting text indexes.
class Tcl_Obj:
    pass
_TextIndex = Union[str, Tcl_Obj]

class Text(Widget):
    def __init__(
        self, master: BaseWidget, *,
        width: int = ...,
        height: int = ...,
        font: _FontSpec = ...,
        borderwidth: int = ...,
        relief: _Relief = ...,
        wrap: _WrapMode = ...,
        state: _TextWidgetState = ...) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['foreground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['background'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['fg'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['bg'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['insertbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['highlightbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['selectforeground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['selectbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['state'], val: _TextWidgetState) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['autoseparators'], val: bool) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['tabs'], val: List[str]) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['yscrollcommand'], val: Callable[[float, float], None]) -> None: ...

    @overload
    def yview(self) -> Tuple[float, float]: ...
    @overload
    def yview(self, /, arg: Literal['moveto'], fraction: float) -> None: ...
    @overload
    def yview(self, /, arg: Literal['scroll'], number: int, what: Union[Literal['units'], Literal['pages']]) -> None: ...
    @overload
    def yview(self, /, arg: Literal['scroll'], number: _ScreenDistance, what: Literal['pixels']) -> None: ...

    def compare(self, index1: _TextIndex, op: _CompareOp, index2: _TextIndex) -> bool: ...
    def delete(self, index1: _TextIndex, index2: Optional[_TextIndex] = ...) -> None: ...
    def edit_reset(self) -> Literal['']: ...
    def edit_separator(self) -> Literal['']: ...
    def get(self, index1: _TextIndex, index2: Optional[_TextIndex] = ...) -> str: ...
    def index(self, index: _TextIndex) -> str: ...
    def mark_set(self, markName: str, index: _TextIndex) -> str: ...
    def peer_create(self, newPathName: str) -> None: ...
    def see(self, index: _TextIndex) -> None: ...

    # actual return type is currently Tcl_Obj which is kinda useless unless
    # str()ed, writing it as _TextIndex to make sure that if it's changed some
    # day then this code won't break
    #
    # the return tuple always has even length because it represents start,end
    # pairs, it's just not nested for some reason
    def tag_ranges(self, tagName: str) -> Tuple[_TextIndex, ...]: ...

    # these functions also take *args, but i have never seen code that uses those *args
    def insert(self, index: _TextIndex, chars: str, /, tag_list: _TagList = ...) -> None: ...
    def tag_add(self, tagName: str, index1: _TextIndex, /, index2: _TextIndex = ...) -> None: ...


class Frame(Widget): pass

_TraceModeString = Union[
    Literal['read'],
    Literal['write'], Literal['unset'],
]
_TraceMode = Union[
    _TraceModeString,
    List[_TraceModeString],
    Tuple[_TraceModeString, ...],
]

class Variable:
    def set(self, value: Any) -> None: ...
    def get(self) -> Any: ...

    # trace is deprecated, please use trace_add instead

    # String arguments that the callback takes (see also trace man page)
    #   - first argument: Tcl variable name
    #   - second argument: seems to be always empty. Don't know how to make non-empty.
    #   - third argument: same as first argument to trace
    def trace_add(self, mode: _TraceMode, callback: Callable[[str, str, str], None]) -> str: ...

class StringVar(Variable):
    def set(self, value: str) -> None: ...
    def get(self) -> str: ...

class IntVar(Variable):
    def set(self, value: int) -> None: ...
    def get(self) -> int: ...

class BooleanVar(Variable):
    def set(self, value: bool) -> None: ...
    def get(self) -> bool: ...

def mainloop() -> None: ...
