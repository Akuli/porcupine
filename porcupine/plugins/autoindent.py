"""Indent new lines automatically when Enter is pressed."""

import dataclasses
import logging
import re
import tkinter
from functools import partial
from typing import Optional, Tuple

from porcupine import get_tab_manager, tabs

# without this, pressing enter twice would strip all trailing whitespace
# from the blank line above the cursor, and then after_enter() wouldn't
# do anything
setup_before = ['rstrip']

log = logging.getLogger(__name__)
SHIFT_FLAG = 1


def leading_whitespace(string: str) -> str:
    r"""Return leading whitespace characters. Ignores trailing '\n'.

    >>> leading_whitespace('\t \t lel')
    '\t \t '
    >>> leading_whitespace('  \n')
    '  '
    """
    count = len(string) - len(string.lstrip())
    return string[:count].rstrip('\n')


@dataclasses.dataclass
class AutoIndentRegexes:
    indent: Optional[str] = None
    dedent: Optional[str] = None


def get_regexes(tab: tabs.FileTab) -> Tuple[str, str]:
    config = tab.settings.get('autoindent_regexes', Optional[AutoIndentRegexes])
    if config is None:
        config = AutoIndentRegexes(None, None)
    assert isinstance(config, AutoIndentRegexes)

    if config.indent is not None:
        try:
            re.compile(config.indent)
        except re.error:
            log.warning(f"invalid indent regex: {config.indent}")
            config.indent = None

    if config.dedent is not None:
        try:
            re.compile(config.dedent)
        except re.error:
            log.warning(f"invalid dedent regex: {config.dedent}")
            config.dedent = None

    return (
        config.indent or r'this regex matches nothing^',
        config.dedent or r'this regex matches nothing^',
    )


def after_enter(tab: tabs.FileTab, shifted: bool) -> None:
    lineno = int(tab.textwidget.index('insert').split('.')[0])
    prevline = tab.textwidget.get(f'{lineno}.0 - 1 line', f'{lineno}.0')

    # we can't strip trailing whitespace before this because then
    # pressing enter twice would get rid of all indentation
    tab.textwidget.insert('insert', leading_whitespace(prevline))

    comment_prefix = tab.settings.get('comment_prefix', Optional[str])
    if comment_prefix is None:
        prevline = prevline.strip()
    else:
        # Not perfect, but should work fine
        prevline = prevline.split(comment_prefix)[0].strip()

    indent_regex, dedent_regex = get_regexes(tab)
    if (prevline.endswith(('(', '[', '{')) or re.fullmatch(indent_regex, prevline)) and not shifted:
        tab.textwidget.indent('insert')
    elif re.fullmatch(dedent_regex, prevline):
        # must be end of a block
        tab.textwidget.dedent('insert')


def on_enter_press(tab: tabs.FileTab, event: 'tkinter.Event[tkinter.Text]') -> None:
    assert isinstance(event.state, int)
    shifted = bool(event.state & SHIFT_FLAG)
    tab.textwidget.after_idle(after_enter, tab, shifted)


def on_closing_brace(tab: tabs.FileTab, event: 'tkinter.Event[tkinter.Text]') -> None:
    # Don't dedent when there's some garbage before cursor, other than comment
    # prefix. It's handy to have autodedent working inside big comments with
    # example code in them.
    before_cursor = tab.textwidget.get('insert linestart', 'insert')
    before_cursor = before_cursor.replace(tab.settings.get('comment_prefix', Optional[str]) or '', '')
    if before_cursor.strip():
        return

    tab.textwidget.dedent('insert')


def on_new_tab(tab: tabs.Tab) -> None:
    if isinstance(tab, tabs.FileTab):
        tab.settings.add_option('autoindent_regexes', None, type=Optional[AutoIndentRegexes])
        tab.textwidget.bind('<Return>', partial(on_enter_press, tab), add=True)
        tab.textwidget.bind('<parenright>', partial(on_closing_brace, tab), add=True)
        tab.textwidget.bind('<bracketright>', partial(on_closing_brace, tab), add=True)
        tab.textwidget.bind('<braceright>', partial(on_closing_brace, tab), add=True)


def setup() -> None:
    get_tab_manager().add_tab_callback(on_new_tab)
