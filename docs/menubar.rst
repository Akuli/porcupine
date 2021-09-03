:mod:`porcupine.menubar` --- The menu bar at the top of the Porcupine window
============================================================================

.. module:: porcupine.menubar

See :ref:`the plugin writing introduction <plugin-intro>` and pretty much
any :source:`plugin that Porcupine comes with <porcupine/plugins>` for example usage.

.. autofunction:: get_menu
.. autofunction:: set_enabled_based_on_tab

.. virtualevent:: Menubar:Foo/Bar/Baz

    Generating an event like this on the main window (see
    :func:`porcupine.get_main_window`) runs the callback of a menu item named
    ``Baz`` in a menu named ``Foo/Bar`` (see :func:`get_menu`).

    Porcupine has a file named ``keybindings.tcl``, and it can be edited at
    *Settings/Config Files* in the menubar.
    By default, it contains a link to Porcupine's default ``keybindings.tcl``,
    and that contains many example key bindings.
    All of them work by associating a keyboard event, such as ``<Control-n>``,
    which one of these virtual events, such as ``<<Menubar:File/New File>>``.

.. autofunction:: add_config_file_button
.. autofunction:: update_keyboard_shortcuts

.. note::

    Menu labels must be ASCII only, because they are used in virtual events.
    Let me know if this limitation bothers you.

    Slashes can be escaped by doubling them. For example, ``"Foobar/Send//Receive"``
    means an entry *Send/Receive* inside a menu named *Foobar*.
