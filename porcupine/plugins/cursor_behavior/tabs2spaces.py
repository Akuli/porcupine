"""Convert tabs to spaces when needed.

This is done by handling all Tab events and forwarding them to
textwidget.MainText.indent and textwidget.MainText.dedent. This plugin
must be loaded after all other plugins that bind tab or shift+tab.
"""

# TODO:
# - language-specificly configurable indentations settings with good
#   defaults (really only needs tabsize + spaces)
# - good support for tabs instead of spaces in rest of the editor

import functools

from porcupine import tabs, utils


def on_tab(event, shift_pressed=False):
    if not event.widget.tag_ranges('sel'):
        # nothing selected
        if shift_pressed:
            event.widget.dedent('insert')
        else:
            event.widget.indent('insert')

    # don't insert a tab when it's not supposed to be inserted, or if
    # shift is pressed down, don't move focus out of the widget
    return 'break'

on_shift_tab = functools.partial(on_tab, shift_pressed=True)   # noqa


def tab_callback(tab):
    if not isinstance(tab, tabs.FileTab):
        yield
        return

    with utils.temporary_bind(tab.textwidget, '<Tab>', on_tab):
        with utils.temporary_bind(tab.textwidget, utils.shift_tab(),
                                  on_shift_tab):
            yield


def setup(editor):
    editor.new_tab_hook.connect(tab_callback)
