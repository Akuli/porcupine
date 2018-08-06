"""Indenting and dedenting automatically."""

# without this, pressing enter twice would strip all trailing whitespace
# from the blank line above the cursor, and then after_enter() wouldn't
# do anything
setup_before = ['rstrip']

from porcupine import get_tab_manager, tabs, utils


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
    lineno = int(textwidget.index('insert').split('.')[0])
    prevline = textwidget.get('%d.0 - 1 line' % lineno, '%d.0' % lineno)
    textwidget.insert('insert', leading_whitespace(prevline))

    # we can't strip trailing whitespace before this because then
    # pressing enter twice would get rid of all indentation
    # TODO: make this language-specific instead of always using python
    #       stuff, but note that some languages like yaml have python-like
    #       indentation-based syntax
    prevline = prevline.strip()
    if prevline.endswith((':', '(', '[', '{')):
        # start of a new block
        textwidget.indent('insert')
    elif (prevline in {'return', 'break', 'pass', 'continue'} or
          prevline.startswith(('return ', 'raise '))):
        # must be end of a block
        textwidget.dedent('insert')


def on_new_tab(event):
    if isinstance(event.data_widget, tabs.FileTab):
        textwidget = event.data_widget.textwidget

        def bind_callback(event):
            textwidget.after_idle(after_enter, textwidget)

        textwidget.bind('<Return>', bind_callback, add=True)


def setup():
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)


if __name__ == '__main__':
    import doctest
    print(doctest.testmod())
