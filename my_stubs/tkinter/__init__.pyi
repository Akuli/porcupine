import os
import sys
import _tkinter
from tkinter import font
from typing import (
    Any,        # use this sparingly lol
    Callable,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

if sys.version_info >= (3, 8):
    from typing import Literal, TypedDict
else:
    from typing_extensions import Literal, TypedDict


# yes, this is a float
TkVersion: float = ...

class TclError(Exception):
    pass

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
    char: str       # can be '??'

_BindCallback = Callable[['Event'], Optional[Literal['break']]]

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
    def __init__(self, master: Optional[Any] = None, value: Optional[Any] = None, name: Optional[str] = None) -> None: ...
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
#
# TODO: rename to _ScreenUnits
_ScreenDistance = Union[str, int, float]

# see 'FONT DESCRIPTIONS' in font man page
# _FontSpec is also used in ttk.pyi
#
# unfortunately Literal inside Tuple doesn't actualyl work... lol
#_FontStyle = Union[
#    Literal['normal'],
#    Literal['bold'],
#    Literal['roman'],
#    Literal['italic'],
#    Literal['underline'],
#    Literal['overstrike'],
#]
_FontStyle = str
_FontSpec = Union[
    str,
    font.Font,

    # ('Helvetica', 16, 'bold')
    # ('Helvetica', 16, ('bold', 'italic'))
    # ('Helvetica', 16, ['bold', 'italic'])
    # ('Helvetica', 16, [])
    Tuple[str, int, _FontStyle],
    Tuple[str, int, Tuple[_FontStyle, ...]],
    Tuple[str, int, List[_FontStyle]],
]

_PackSide = Union[Literal['left'], Literal['right'], Literal['top'], Literal['bottom']]
_PackFill = Union[Literal['none'], Literal['x'], Literal['y'], Literal['both']]
_PackPad = Union[
    Tuple[_ScreenDistance, _ScreenDistance],    # (top, bottom) or (left, right)
    _ScreenDistance,                    # same value used for both
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
        file: Union[os.PathLike[str], os.PathLike[bytes]] = ...,
        width: int = ...,
        height: int = ...,
    ) -> None: ...
    def width(self) -> int: ...
    def height(self) -> int: ...

T1 = TypeVar('T1')
T2 = TypeVar('T2')
T3 = TypeVar('T3')
T4 = TypeVar('T4')
T5 = TypeVar('T5')

# FIXME: some widgets are Misc but not BaseWidget
# FIXME: lots of BaseWidget stuff should be in Misc instead
class Misc:
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
    def bind_class(self, className: Any, sequence: Any=..., func: Callable[..., Any] = ..., add: Any = ...) -> Optional[str]: ...

    # The data is str()ed, and it can be anything that has valid str().
    def event_generate(
        self, sequence: str, *,
        x: int = ...,
        y: int = ...,
        data: Any = ...,
    ) -> None: ...

    def grid_size(self) -> Tuple[int, int]: ...

    def winfo_children(self) -> List[Misc]: ...


class BaseWidget(Misc):
    master: Optional[Misc]

    # I don't think this is documented, but MANY sources online use this
    # occationally. Tkinter itself uses this everywhere.
    tk: _tkinter.TkappType

    # TODO: is there some way to avoid the copy/pasta or support an arbitrary
    # number of arguments?
    @overload
    def after(self, ms: int, func: Callable[[                  ], None]                                                            ) -> str: ...
    @overload
    def after(self, ms: int, func: Callable[[T1                ], None], __arg1: T1                                                ) -> str: ...
    @overload
    def after(self, ms: int, func: Callable[[T1, T2            ], None], __arg1: T1, __arg2: T2                                    ) -> str: ...
    @overload
    def after(self, ms: int, func: Callable[[T1, T2, T3        ], None], __arg1: T1, __arg2: T2, __arg3: T3                        ) -> str: ...
    @overload
    def after(self, ms: int, func: Callable[[T1, T2, T3, T4    ], None], __arg1: T1, __arg2: T2, __arg3: T3, __arg4: T4            ) -> str: ...
    @overload
    def after(self, ms: int, func: Callable[[T1, T2, T3, T4, T5], None], __arg1: T1, __arg2: T2, __arg3: T3, __arg4: T4, __arg5: T5) -> str: ...

    @overload
    def after_idle(self, func: Callable[[                  ], None]                                                            ) -> str: ...
    @overload
    def after_idle(self, func: Callable[[T1                ], None], __arg1: T1                                                ) -> str: ...
    @overload
    def after_idle(self, func: Callable[[T1, T2            ], None], __arg1: T1, __arg2: T2                                    ) -> str: ...
    @overload
    def after_idle(self, func: Callable[[T1, T2, T3        ], None], __arg1: T1, __arg2: T2, __arg3: T3                        ) -> str: ...
    @overload
    def after_idle(self, func: Callable[[T1, T2, T3, T4    ], None], __arg1: T1, __arg2: T2, __arg3: T3, __arg4: T4            ) -> str: ...
    @overload
    def after_idle(self, func: Callable[[T1, T2, T3, T4, T5], None], __arg1: T1, __arg2: T2, __arg3: T3, __arg4: T4, __arg5: T5) -> str: ...

    def after_cancel(self, id: str) -> None: ...

    def focus_get(self) -> Optional[Misc]: ...

    def clipboard_clear(self) -> None: ...
    def clipboard_append(self, string: str) -> None: ...
    def deletecommand(self, name: str) -> None: ...
    def destroy(self) -> None: ...

    def focus_set(self) -> None: ...
    def getvar(self, name: str = ...) -> Any: ...    # doesn't always return str
    def grid_columnconfigure(
        self, index: int, *,
        minsize: _ScreenDistance = ...,
        weight: int = ...,
        uniform: str = ...,
        pad: _ScreenDistance = ...,
    ) -> None: ...
    # name is str()ed, can be anything with sane str() that tkinter outputs
    def nametowidget(self, name: Union[str, Misc, _tkinter.Tcl_Obj]) -> Misc: ...

    # register() callbacks can do pretty much anything, can't do more specific type hints
    def register(self, func: Callable[..., Any]) -> str: ...

    def update(self) -> None: ...
    def wait_window(self) -> None: ...
    def winfo_ismapped(self) -> Union[Literal[0], Literal[1]]: ...  # weird that its not bool
    def winfo_rgb(self, color: str) -> Tuple[int, int, int]: ...
    def winfo_rootx(self) -> int: ...
    def winfo_rooty(self) -> int: ...
    def winfo_toplevel(self) -> Union['Tk', 'Toplevel']: ...
    def winfo_width(self) -> int: ...
    def winfo_height(self) -> int: ...
    def winfo_reqwidth(self) -> int: ...
    def winfo_reqheight(self) -> int: ...
    def winfo_screenwidth(self) -> int: ...
    def winfo_screenheight(self) -> int: ...
    def winfo_x(self) -> int: ...
    def winfo_y(self) -> int: ...

# all strings containing some of 'n', 's', 'w', 'e' with no duplicates
_Sticky = Union[
    Literal[''],
    Literal['n'], Literal['s'], Literal['w'], Literal['e'],
    Literal['ns'], Literal['nw'], Literal['ne'],
    Literal['sn'], Literal['sw'], Literal['se'],
    Literal['wn'], Literal['ws'], Literal['we'],
    Literal['en'], Literal['es'], Literal['ew'],
    Literal['nsw'], Literal['nse'], Literal['nws'], Literal['nwe'], Literal['nes'], Literal['new'],
    Literal['snw'], Literal['sne'], Literal['swn'], Literal['swe'], Literal['sen'], Literal['sew'],
    Literal['wns'], Literal['wne'], Literal['wsn'], Literal['wse'], Literal['wen'], Literal['wes'],
    Literal['ens'], Literal['enw'], Literal['esn'], Literal['esw'], Literal['ewn'], Literal['ews'],
    Literal['nswe'], Literal['nsew'], Literal['nwse'], Literal['nwes'], Literal['nesw'], Literal['news'],
    Literal['snwe'], Literal['snew'], Literal['swne'], Literal['swen'], Literal['senw'], Literal['sewn'],
    Literal['wnse'], Literal['wnes'], Literal['wsne'], Literal['wsen'], Literal['wens'], Literal['wesn'],
    Literal['ensw'], Literal['enws'], Literal['esnw'], Literal['eswn'], Literal['ewns'], Literal['ewsn'],
]

class _GridInfo(TypedDict, total=False):
    row: int

# this class represents a widget that can be put inside another widget
class Widget(BaseWidget):

    # Toplevel and Tk are BaseWidgets but not Widgets. They also have master
    # but it's often None and not so useful. This is never None as far as I
    # know.
    master: Misc

    # these methods are actually in 3 separate classes: Pack, Grid, Place,
    # but there should never be any need to use those directly so why bother
    # with them here
    def __init__(self, master: Misc) -> None: ...

    def grid(
        self, *,
        column: int = ...,
        columnspan: int = ...,
        row: int = ...,
        rowspan: int = ...,
        sticky: _Sticky = ...,
        # TODO: figure out how 'in' is supposed to work
        ipadx: _ScreenDistance = ...,
        ipady: _ScreenDistance = ...,
        # pad tuple means different paddings for left and right, or top and bottom
        padx: Union[_ScreenDistance, Tuple[_ScreenDistance, _ScreenDistance]] = ...,
        pady: Union[_ScreenDistance, Tuple[_ScreenDistance, _ScreenDistance]] = ...,
    ) -> None: ...
    def grid_info(self) -> _GridInfo: ...

    def pack(
        self, *,
        side: _PackSide = ...,
        fill: _PackFill = ...,
        anchor: _Anchor = ...,
        expand: bool = ...,
        # pad tuple means different paddings for left and right, or top and bottom
        padx: Union[_ScreenDistance, Tuple[_ScreenDistance, _ScreenDistance]] = ...,
        pady: Union[_ScreenDistance, Tuple[_ScreenDistance, _ScreenDistance]] = ...
    ) -> None: ...
    def pack_forget(self) -> None: ...

    def place(
        self, *,
        x: _ScreenDistance = ...,
        y: _ScreenDistance = ...,
        width: _ScreenDistance = ...,
        height: _ScreenDistance = ...,
        relx: float = ...,
        rely: float = ...,
        relwidth: float = ...,
        relheight: float = ...,
        anchor: _Anchor = ...,
    ) -> None: ...

class Label(Widget):
    def __init__(
        self, master: Misc, *,
        text: str = ...,
        border: int = ...,
        fg: str = ...,
        bg: str = ...,
        image: PhotoImage = ...,
        cursor: str = ...,
    ) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['text'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['wraplength'], val: _ScreenDistance) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['font'], val: _FontSpec) -> None: ...

# see menu man page for what kind of strings are allowed
_MenuIndex = Union[int, str]

class Menu(Widget):
    def __init__(self, *, tearoff: bool = ...) -> None: ...
    def entryconfig(
        self, index: _MenuIndex, *,
        state: Union[Literal['normal'], Literal['active'], Literal['disabled']],
    ) -> None: ...
    def index(self, index: _MenuIndex) -> Optional[int]: ...
    def insert_cascade(
        self, index: _MenuIndex, *,
        label: str = ...,
        accelerator: str = ...,
        menu: 'Menu' = ...,
    ) -> None: ...
    def add_cascade(
        self, *, label: str = ..., accelerator: str = ...,
        menu: 'Menu' = ...,
    ) -> None: ...
    def add_command(
        self, *, label: str = ..., accelerator: str = ...,
        command: Callable[[], None],
    ) -> None: ...
    def add_checkbutton(
        self, *, label: str = ..., accelerator: str = ...,
        variable: BooleanVar = ...,
    ) -> None: ...
    def add_radiobutton(
        self, *, label: str = ..., accelerator: str = ...,
        variable: StringVar = ...,
    ) -> None: ...

class YView:
    @overload
    def yview(self) -> Tuple[float, float]: ...
    @overload
    def yview(self, __arg: Literal['moveto'], __fraction: float) -> None: ...
    @overload
    def yview(self, __arg: Literal['scroll'], __number: int, __what: Union[Literal['units'], Literal['pages']]) -> None: ...
    @overload
    def yview(self, __arg: Literal['scroll'], __number: _ScreenDistance, __what: Literal['pixels']) -> None: ...

    # i wish there was an easy way to do partialmethods
    @overload
    def yview_scroll(self, __number: int, __what: Union[Literal['units'], Literal['pages']]) -> None: ...
    @overload
    def yview_scroll(self, __number: _ScreenDistance, __what: Literal['pixels']) -> None: ...

    def yview_moveto(self, __fraction: float) -> None: ...

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
_TextIndex = Union[str, _tkinter.Tcl_Obj]

class Text(Widget, YView):
    def __init__(
        self, master: Misc, *,
        exportselection: bool = ...,
        takefocus: bool = ...,
        yscrollcommand: Union[str, Callable[[str, str], None]] = ...,
        width: int = ...,
        height: int = ...,
        font: _FontSpec = ...,
        borderwidth: int = ...,
        relief: _Relief = ...,
        wrap: _WrapMode = ...,
        state: _TextWidgetState = ...) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['width'], val: int) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['exportselection'], val: bool) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['takefocus'], val: bool) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['wrap'], val: _WrapMode) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['foreground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['background'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['fg'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['bg'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['selectforeground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['selectbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['inactiveselectbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['insertbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['highlightbackground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['highlightcolor'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['highlightthickness'], val: _ScreenDistance) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['state'], val: _TextWidgetState) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['autoseparators'], val: bool) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['tabs'], val: Union[str, _ScreenDistance, Tuple[Union[str, _ScreenDistance], ...]]) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['cursor'], val: str) -> None: ...
    # TODO: belongs to YView but is currently copy/pasted to every subclasses
    @overload
    def __setitem__(self, opt: Literal['yscrollcommand'], val: Union[str, Callable[[str, str], None]]) -> None: ...

    def __getitem__(self, opt: Literal['font', 'yscrollcommand']) -> Any: ...

    def bbox(self, index: _TextIndex) -> Optional[Tuple[int, int, int, int]]: ...
    def compare(self, index1: _TextIndex, op: _CompareOp, index2: _TextIndex) -> bool: ...
    def delete(self, index1: _TextIndex, index2: Optional[_TextIndex] = ...) -> None: ...
    def edit_reset(self) -> Literal['']: ...
    def edit_separator(self) -> Literal['']: ...
    def get(self, index1: _TextIndex, index2: Optional[_TextIndex] = ...) -> str: ...
    def index(self, index: _TextIndex) -> str: ...
    def mark_set(self, markName: str, index: _TextIndex) -> str: ...
    def peer_create(self, newPathName: Union[str, Text]) -> None: ...
    def peer_names(self) -> List[_tkinter.Tcl_Obj]: ...
    def search(
        self, pattern: str, index: _TextIndex, stopindex: _TextIndex = ..., *,
        forwards: bool = ...,
        backwards: bool = ...,
        exact: bool = ...,
        regexp: bool = ...,
        nocase: bool = ...,
        elide: bool = ...,
        count: IntVar = ...,
    ) -> str: ...       # returns empty string for no match

    def see(self, index: _TextIndex) -> None: ...
    def tag_bind(self, tagName: str, sequence: str, func: _BindCallback, add: bool = ...) -> str: ...
    def tag_cget(self, tagName: str, option: Literal['font']) -> str: ...
    def tag_config(
        self, tagName: str, *,
        foreground: str = ...,
        background: str = ...,
        underline: bool = ...,
        font: _FontSpec = ...,
    ) -> None: ...
    def tag_lower(self, tagName: str, belowThis: str = ...) -> None: ...
    def tag_remove(self, tagName: str, index1: _TextIndex, index2: _TextIndex = ...) -> None: ...

    # actual return type is currently Tcl_Obj which is kinda useless unless
    # str()ed, writing it as _TextIndex to make sure that if it's changed some
    # day then this code won't break
    #
    # the return tuple always has even length because it represents start,end
    # pairs, it's just not nested for some reason
    def tag_ranges(self, tagName: str) -> Tuple[_TextIndex, ...]: ...

    # these functions also take *args, but i have never seen code that uses
    # those *args differently than what's supported here
    def insert(self, index: _TextIndex, chars: str, __tag_list: _TagList = ...) -> None: ...
    def replace(self, index1: _TextIndex, index2: _TextIndex, chars: str) -> None: ...
    def tag_add(self, tagName: str, index1: _TextIndex, __index2: _TextIndex = ...) -> None: ...

class Frame(Widget):
    def __init__(
        self, master: Misc, *,
        width: _ScreenDistance = ...,
        height: _ScreenDistance = ...,
    ) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['foreground'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['background'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['fg'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['bg'], val: str) -> None: ...

# TODO: what other protocol names are there?
#       are some of these deprecated or supported only on some platforms?
_WmProtocolName = Union[
    Literal['WM_DELETE_WINDOW'],
    Literal['WM_SAVE_YOURSELF'],
    Literal['WM_TAKE_FOCUS'],
]

# see 'wm state' in wm man page
_WmState = Union[
    Literal['normal'],
    Literal['icon'],
    Literal['iconic'],
    Literal['withdrawn'],
    Literal['zoomed'],
]

_StupidBool = Union[Literal[0], Literal[1]]

# stuff for Toplevel and Tk
class Wm:
    # TODO: overload other ways to call attributes()
    def attributes(self, __opt: Literal['-fullscreen'], __val: bool) -> Literal['']: ...

    @overload
    def geometry(self) -> str: ...
    @overload
    def geometry(self, newGeometry: str) -> Literal['']: ...

    @overload
    def state(self) -> _WmState: ...
    @overload
    def state(self, newstate: _WmState) -> Literal['']: ...

    @overload
    def minsize(self) -> Tuple[int, int]: ...
    @overload
    def minsize(self, width: int, height: int) -> None: ...

    @overload
    def resizable(self) -> Tuple[_StupidBool, _StupidBool]: ...
    @overload
    def resizable(self, width: bool, height: bool) -> Literal['']: ...

    def overrideredirect(self, boolean: bool) -> None: ...
    def protocol(self, name: _WmProtocolName, func: Callable[[], None]) -> Literal['']: ...
    def title(self, string: str) -> Literal['']: ...
    def transient(self, master: Wm) -> Literal['']: ...
    def withdraw(self) -> None: ...   # actually returns empty string
    def deiconify(self) -> Literal['']: ...

    def __setitem__(self, opt: Literal['menu'], val: Menu) -> None: ...

class Toplevel(BaseWidget, Wm): pass

class Tk(BaseWidget, Wm):
    # actually many widgets have this, but invoking it elsewhere doesn't make
    # much sense
    def mainloop(self) -> None: ...

def mainloop() -> None: ...
