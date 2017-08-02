"""Convert tabs to spaces when needed.

This is done by handling all Tab events and forwarding them to
textwidget.MainText.indent and textwidget.MainText.dedent. This plugin
must be loaded after all other plugins that bind tab or shift+tab.
"""

import porcupine
from porcupine import tabs, utils


def on_tab(event, shift_pressed):
    if not event.widget.tag_ranges('sel'):
        # nothing selected
        if shift_pressed:
            event.widget.dedent('insert')
        else:
            event.widget.indent('insert')

    # don't insert a tab when it's not supposed to be inserted, or if
    # shift is pressed down, don't move focus out of the widget
    return 'break'


def tab_callback(tab):
    if isinstance(tab, tabs.FileTab):
        with utils.temporary_tab_bind(tab.textwidget, on_tab):
            yield
    else:
        yield


def setup():
    porcupine.get_tab_manager().new_tab_hook.connect(tab_callback)
