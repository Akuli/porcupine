from __future__ import annotations

import tkinter
from abc import abstractmethod

from porcupine import textutils


class BaseHighlighter:
    """This class defines what all syntax highlighters must do.

    A syntax highlighter can have internal state that depends on the text
    widget, e.g. an AST tree. The highlighter's __init__() should initialize
    that state from what is currently in the text widget, and afterwards it
    should be updated based on change events.

    Once the internal state is up to date, the highlighter should be able to
    turn it into tags for the text widget. That's what add_tags() does. What
    color each tag gets depends on the current pygments theme and is configured
    in a separate plugin.
    """

    def __init__(self, textwidget: tkinter.Text) -> None:
        self.textwidget = textwidget
        textutils.use_pygments_tags(self.textwidget)

    @abstractmethod
    def update_internal_state(self, changes: textutils.Changes) -> None:
        raise NotImplementedError

    # It's fine if some tags end up outside the given range
    @abstractmethod
    def add_tags(self, start: str, end: str) -> None:
        raise NotImplementedError
