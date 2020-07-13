from typing import Any

class Tcl_Obj:
    pass

# the __name__ of this class is 'tkapp', but it's available as
# _tkinter.TkappType
#
# example:
#
#    >>> import tkinter, _tkinter
#    >>> tkapp = tkinter.Tk().tk
#    >>> tkapp
#    <_tkinter.tkapp object at 0x7f81fe7edd30>
#    >>> isinstance(tkapp, _tkinter.TkappType)
#    True
#    >>> tkapp.call('set', 'foo', (1,2,3))
#    (1, 2, 3)
#    >>> tkapp.eval('return $foo')
#    '1 2 3'
#    >>>
#
# TODO: tkinter has __getattr__ hacks that make some_widget.foo equivalent to
#       some_widget.tk.foo, so all widgets have call and eval methods. Should
#       that be supported?
class TkappType:

    # Arguments can be any objects, and they typically get str()ed. That isn't
    # always the case though. For example, a tuple means a Tcl list (see
    # example below).
    def call(self, command: str, *args: Any) -> Any: ...

    # TODO: does this always return string like in above example?
    def eval(self, command: str) -> Any: ...
