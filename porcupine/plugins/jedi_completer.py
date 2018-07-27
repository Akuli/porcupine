"""Python autocompletion with Jedi.

You need jedi if you want to use this module. Install it like this on
Windows::

    py -m pip install --user jedi

Or like this on other operating systems::

    python3 -m pip install --user jedi
"""

import logging
import os
from porcupine import dirs, get_tab_manager, tabs, utils
from porcupine.plugins import autocomplete

try:
    import jedi
except ImportError:
    # the space after the last \n is intentional, logging strips off
    # trailing newlines
    logging.getLogger(__name__).exception(
        "Jedi is not installed. You can install it like this:\n\n" +
        "    %s -m pip install --user jedi\n ", utils.short_python_command)
    jedi = None


def jedi_completer(tab):
    source = tab.textwidget.get("1.0", "end - 1 char")
    cursor_pos = tab.textwidget.index("insert")
    line, column = map(int, cursor_pos.split("."))

    # the source is already unicode, so jedi doesn't need an encoding
    script = jedi.Script(source, line, column, path=tab.path)
    suffixes = (c.complete for c in script.completions())
    return ((cursor_pos, cursor_pos, suffix) for suffix in suffixes)


def on_filetype_changed(event, *, tab=None):
    if tab is None:
        tab = event.widget

    if tab.filetype.name == 'Python':
        print("Jedi Completer Enabled")
        tab.completer = jedi_completer
    else:
        print("Jedi Completer Disabled")
        if tab.completer is jedi_completer:
            tab.completer = None


def on_new_tab(event):
    tab = event.data_widget
    tab.bind('<<FiletypeChanged>>', on_filetype_changed, add=True)
    on_filetype_changed(None, tab=tab)


def setup():
    if jedi is not None:
        jedi.settings.cache_directory = os.path.join(dirs.cachedir, 'jedi')
        jedi.settings.case_insensitive_completion = False
        utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab,
                             add=True)
