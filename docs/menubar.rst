:mod:`porcupine.menubar` --- The menu bar at the top of the Porcupine window
============================================================================

.. module:: porcupine.menubar

See :ref:`the plugin writing introduction <plugin-intro>` and pretty much
any :source:`plugin that Porcupine comes with <porcupine/plugins>` for example usage.

.. autofunction:: get_menu
.. autofunction:: set_enabled_based_on_tab

.. virtualevent:: Menubar:Foo/Bar/Baz

    Generating an event like this on the main window (see
    :func:`porcupine.get_main_window`)runs the callback of a menu item named
    ``Baz`` in a menu named ``Foo/Bar`` (see :func:`get_menu`).

    Use the ``event_add()`` method of any tkinter widget to associate a
    keyboard shortcut with the menu item. For example, Porcupine runs code like
    this when it starts::

        main_window = get_main_window()
        main_window.event_add('<<Menubar:File/New File>>', '<Control-n>')
        main_window.event_add('<<Menubar:File/Open>>', '<Control-o>')
        main_window.event_add('<<Menubar:File/Save>>', '<Control-s>')
        main_window.event_add('<<Menubar:File/Save As>>', '<Control-S>')
        ...

    Call :func:`update_keyboard_shortcuts` after doing that.

.. autofunction:: update_keyboard_shortcuts
