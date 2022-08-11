from __future__ import annotations

import tkinter
from abc import abstractmethod
from typing import Any, Iterator

from pygments import token

from porcupine import textutils


def _list_all_token_types(tokentype: Any) -> Iterator[Any]:
    yield tokentype
    for sub in map(_list_all_token_types, tokentype.subtypes):
        yield from sub


_all_token_tags = set(map(str, _list_all_token_types(token.Token)))


class BaseHighlighter:
    """This class defines what all syntax highlighters must do.

    A syntax highlighter has to:
    - Highlight the visible part of the file when the highlighter is enabled.
        * When the highlighter has been created (and __init__() has ran), on_scroll()
          will be called automatically. This means that you can do some of the initial
          highlighting with on_scroll().
    - Update the visible part of the file when the user scrolls the file.
    - Update the visible part of the file when it is edited.

    The concrete highlighter subclasses decide how exactly this is done, but
    this base class provides utilities to help with it.
    """

    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)

    @abstractmethod
    def on_scroll(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_change(self, changes: textutils.Changes) -> None:
        raise NotImplementedError

    def get_visible_part(self) -> tuple[str, str]:
        start = self.textwidget.index("@0,0")
        end = self.textwidget.index("@0,10000")
        return (start, end)

    def delete_tags(self, start: str, end: str) -> None:
        for tag in _all_token_tags:
            self.textwidget.tag_remove(tag, start, end)
