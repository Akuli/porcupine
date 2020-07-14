import sys
import tkinter
from typing import (
    Any,    # use sparingly lol
    Dict,
    Tuple,
    Union,
    overload,
)

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


class Font:
    def __init__(
        self, *,
        name: str = ...,
        exists: bool = ...,
        family: str = ...,
        size: int = ...,
        weight: Union[Literal['normal'], Literal['bold']] = ...,
        slant: Union[Literal['roman'], Literal['italic']] = ...,
    ) -> None: ...

    @overload
    def __setitem__(self, opt: Literal['family'], val: str) -> None: ...
    @overload
    def __setitem__(self, opt: Literal['size'], val: int) -> None: ...

    @overload
    def actual(self) -> Dict[str, Any]: ...
    @overload
    def actual(self, option: Literal['family']) -> str: ...

    def measure(self, text: str) -> int: ...


def families(root: tkinter.Tk = ...) -> Tuple[str, ...]: ...
