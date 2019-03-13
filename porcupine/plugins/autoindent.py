"""Indenting and dedenting automatically when enter is pressed."""

import teek as tk

from porcupine import get_tab_manager, tabs, utils

# without this, pressing enter twice would strip all trailing whitespace
# from the blank line above the cursor, and then after_enter() wouldn't
# do anything
setup_before = ['rstrip']


def leading_whitespace(string):
    r"""Return leading whitespace characters. Ignores trailing '\n'.

    >>> leading_whitespace('\t \t lel')
    '\t \t '
    >>> leading_whitespace('  \n')
    '  '
    """
    count = len(string) - len(string.lstrip())
    return string[:count].rstrip('\n')


def after_enter(textwidget):
    """Indent or dedent the current line automatically if needed."""
    linestart = textwidget.marks['insert'].linestart()
    prevline = textwidget.get(linestart.back(lines=1), linestart)
    textwidget.insert(textwidget.marks['insert'], leading_whitespace(prevline))

    # we can't strip trailing whitespace before this because then
    # pressing enter twice would get rid of all indentation
    # TODO: make this language-specific instead of always using python
    #       stuff, but note that some languages like yaml have python-like
    #       indentation-based syntax
    prevline = prevline.strip()
    if prevline.endswith((':', '(', '[', '{')):
        # start of a new block
        textwidget.indent(textwidget.marks['insert'])
    elif (prevline in {'return', 'break', 'pass', 'continue'} or
          prevline.startswith(('return ', 'raise '))):
        # must be end of a block
        textwidget.dedent(textwidget.marks['insert'])


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        def bind_callback():
            tk.after_idle(after_enter, args=[tab.textwidget])

        tab.textwidget.bind('<Return>', bind_callback)


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
