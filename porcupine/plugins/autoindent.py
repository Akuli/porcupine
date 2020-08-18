"""Indent new lines automatically when Enter is pressed."""

import tkinter

from porcupine import get_tab_manager, tabs, textwidget, utils

# without this, pressing enter twice would strip all trailing whitespace
# from the blank line above the cursor, and then after_enter() wouldn't
# do anything
setup_before = ['rstrip']


def leading_whitespace(string: str) -> str:
    r"""Return leading whitespace characters. Ignores trailing '\n'.

    >>> leading_whitespace('\t \t lel')
    '\t \t '
    >>> leading_whitespace('  \n')
    '  '
    """
    count = len(string) - len(string.lstrip())
    return string[:count].rstrip('\n')


def after_enter(text: textwidget.MainText) -> None:
    """Indent or dedent the current line automatically if needed."""
    lineno = int(text.index('insert').split('.')[0])
    prevline = text.get(f'{lineno}.0 - 1 line', f'{lineno}.0')
    text.insert('insert', leading_whitespace(prevline))

    # we can't strip trailing whitespace before this because then
    # pressing enter twice would get rid of all indentation
    # TODO: make this language-specific instead of always using python
    #       stuff, but note that some languages like yaml have python-like
    #       indentation-based syntax
    prevline = prevline.strip()
    if prevline.endswith((':', '(', '[', '{')):
        # start of a new block
        text.indent('insert')
    elif (prevline in {'return', 'break', 'pass', 'continue'} or
          prevline.startswith(('return ', 'raise '))):
        # must be end of a block
        text.dedent('insert')


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        def bind_callback(event: 'tkinter.Event[tkinter.Misc]') -> None:
            assert isinstance(tab, tabs.FileTab)   # because mypy is awesome
            tab.textwidget.after_idle(after_enter, tab.textwidget)

        tab.textwidget.bind('<Return>', bind_callback, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
