import tkinter
from typing import (
    Any,    # use sparingly lol
    Dict,
    Literal,
    Tuple,
    Union,
    overload,
)


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
