"""Convert tabs to spaces when needed.

.. note::
    This plugin binds Tab and Shift-Tab, and always returns ``'break'``.
    If you are writing a plugin that binds Tab or Shift-Tab too, it
    **must** be set up before this plugin. For example::

        setup_before = ['tabs2spaces']

    As a side note, if your plugin binds ``<Shift-Tab>`` it should
    probably use :func:`porcupine.utils.bind_tab_key` instead.
"""

# TODO: should this even be a plugin? the actual tabs to spaces conversion is
#       done by indent() and dedent(), and this just makes sure that they are
#       called when tab is pressed

import pythotk as tk

from porcupine import get_tab_manager, tabs, utils


def on_tab(shift_pressed, event):
    if not event.widget.get_tag('sel').ranges():
        # nothing selected
        if shift_pressed:
            event.widget.dedent(event.widget.marks['insert'])
        else:
            event.widget.indent(event.widget.marks['insert'])

    # don't insert a tab when it's not supposed to be inserted, or if
    # shift is pressed down, don't move focus out of the widget
    return 'break'


def on_new_tab(tab):
    if isinstance(tab, tabs.FileTab):
        tk.extras.bind_tab_key(tab.textwidget, on_tab, event=True)


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
