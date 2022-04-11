:mod:`porcupine.settings` --- Porcupine's setting manager
=========================================================

.. module:: porcupine.settings

This module manages Porcupine's settings and the *Porcupine Settings* dialog
in the *Edit* menu.

.. |triangle| image:: ../porcupine/images/triangle.gif


Global and non-global settings
------------------------------

.. data:: global_settings

    You often need only this variable from the ``porcupine.settings`` module.
    It's a :class:`Settings` object that contains all settings that are the same everywhere in Porcupine.
    For example, it doesn't contain settings like "indentation is 4 spaces", which can be different in each tab.

.. class:: Settings

    Each instance of :class:`Settings` is basically a dict of option names and values,
    but it does more than that;
    it ensures that the values have the correct type,
    converts them to the correct type when loaded from a setting file,
    and so on.

    There are two kinds of instances of this class that you will likely come across:

        * The :data:`global_settings` object.
        * Each :class:`~porcupine.tabs.FileTab` has its own :class:`Settings` object,
          known as :attr:`porcupine.tabs.FileTab.settings`.


.. |br| raw:: html

    <br />

Porcupine has these options in ``global_settings`` by default (but you can add your own options too, see below):

    ``font_family``: :class:`str` |br| ``font_size``: :class:`int`
        The font family and size used in Porcupine's main text widget.


        Porcupine also keeps these settings in a special font named
        ``TkFixedFont``, so if you want to use this font in a widget just
        pass it a ``font='TkFixedFont'`` option. ``Text`` widgets use
        ``TkFixedFont`` by default.

        Do this if you need a ``Font`` object instead of the font name as a
        string::

            import tkinter.font
            fixedfont = tkinter.font.Font(name='TkFixedFont', exists=True)

    ``pygments_style``: :class:`str`
        Name of the current Pygments style used for syntax highlighting.
        Use this option like this::

            from porcupine import settings
            from pygments import styles
            the_style = styles.get_style_by_name(settings.get('pygments_style', str))

    ``disabled_plugins``: list[:class:`str`]

        Names of plugins that the user has disabled. See :mod:`porcupine.pluginloader`.

    ``default_line_end``: :class:`LineEnding`

        The default line ending for new files.

.. autoclass:: LineEnding


Getting and Setting
-------------------

Use these methods on ``global_settings`` (or other :class:`Settings` objects) for setting and getting values:

.. automethod:: Settings.set

.. method:: Settings.get(option_name, type)

    Return the current value of an option.
    The *type* should be e.g. ``str`` or ``int`` depending on what type the option is.
    You can also specify ``object`` to allow any type.

    I have tried to tell mypy that this method returns a value
    of the given *type*.
    Mypy understands that in many cases, but not always::

        foo = settings.get('foo', str)
        reveal_type(foo)  # str

        from pathlib import Path
        shitty_bar = settings.get('bar', Optional[Path])
        reveal_type(shitty_bar)  # Any

    Use a type annotation to work around this (and make sure to write the
    same type two times)::

        good_bar: Path | None = settings.get('bar', Optional[Path])
        reveal_type(good_bar)  # Optional[Path]

    Before Python 3.10, you can't use the new ``|`` syntax as an argument to ``settings.get()``,
    even though it otherwise works with ``from __future__ import annotations``.
    The same goes for built-in generics,
    such as ``list[str]`` with lower-case ``list``.

    Options of mutable types are returned as copies, so things like
    ``settings.get('something', List[str])`` always return a new list.
    If you want to change a setting like that, you need to first get a copy
    of the current value, then modify the copy, and finally :meth:`set` it
    back. This is an easy way to make sure that change events run every
    time the value changes.

.. automethod:: Settings.debug_dump


Custom Options
--------------

Use :data:`global_settings` to store things that shouldn't reset every
time Porcupine is restarted.

.. automethod:: Settings.add_option

Example::

    import logging
    from porcupine.settings import global_settings

    log = logging.getLogger(__name__)

    def connect_to_http_server() -> None:
        host = global_settings.get('http_server_host', str)
        port = global_settings.get('http_server_port', int)
        log.info(f"Connecting to {host}:{port}...")
        ...

    def setup() -> None:
        # 80 and '127.0.0.1' are default values
        global_settings.add_option('http_server_host', '127.0.0.1')
        global_settings.add_option('http_server_port', 80)

As the name suggests, the global settings are shared by all plugins,
so don't make the option names too short.
For example, if two plugins define an option named ``port``,
then one of them will get an error from :func:`add_option` when the plugins get set up.
If the plugins had instead named their options e.g. ``langserver_port`` and ``http_server_port``,
then there would be no problem.

.. note::
    Porcupine stores the global settings in a JSON file, but that file isn't meant to be
    edited directly by users. Instead, please provide some way to change the
    settings with a GUI, such as a handle that can be dragged to change the size
    settings of a widget, or add something to the setting dialog (see below).


The Settings Dialog
-------------------

Click *Porcupine Settings* in the *Edit* menu to open the dialog.
It is meant to be used for editing :data:`global_settings`.

.. autofunction:: get_dialog_content

You can add widgets to the content frame, but it's usually easiest to use these functions.
All of these return the added widget.
A label that displays *text* is added to column 0 (see the ascii art above).
When setting the values, the converter passed to :func:`add_option` is used.

.. note::

    The *option_name* argument of the functions below
    must be an existing option on :data:`global_settings`.
    You can create it just before calling the functions below::

        from porcupine import settings
        from porcupine.settings import global_settings

        def validate_host(host: str) -> bool:
            ...

        ...

        global_settings.add_option('http_server_host', '127.0.0.1')
        settings.add_entry('http_server_host', "HTTP server host:", validate_callback)


.. autofunction:: add_entry
.. autofunction:: add_checkbutton
.. autofunction:: add_combobox
.. autofunction:: add_spinbox
.. autofunction:: add_label


Change Events
-------------

.. virtualevent:: GlobalSettingChanged:foo

    When any global setting is changed,
    all widgets in the main window (see :func:`porcupine.get_main_window`)
    receive a virtual event named ``<<GlobalSettingChanged:option_name>>``,
    where ``option_name`` is the name of the changed setting.
    For example, ``<<GlobalSettingChanged:pygments_style>>`` runs
    when the user changes the Pygments style.

All widget bindings go away automatically when the corresponding widget is destroyed.
For example, if you want to update the configuration of a :class:`tkinter.Text` widget when ``pygments_style`` changes,
you should use the ``.bind()`` method of that text widget.
This way your callback won't be called when the text widget doesn't exist anymore.

If you want your binding to work as long as Porcupine is running,
use the bind method of :func:`porcupine.get_tab_manager`.

.. note::
    Do not use :func:`porcupine.get_main_window` for binding to ``<<GlobalSettingChanged:foo>>``.
    The main window is a :class:`tkinter.Tk` widget,
    so it gets notified of its child widgets' events too.
    (The same applies to :class:`tkinter.Toplevel`.)
    For example, let's say that  there are 100 widgets currently being shown in the main window,
    and you unwisely use the main window's ``bind()`` to bind ``<<GlobalSettingChanged:foo>>``.
    When the ``foo`` setting changes, your bind callback runs
    100 times with ``event.widget`` set to something else than the main window, and
    once with ``event.widget`` set to the main window.
    This can cause annoying slowness.

Other :class:`Settings` objects use a different name for the change events,
and unlike :class:`global_settings`, don't emit the change events on all widgets.
For example, the change event of tab-specific settings is named
:virtevt:`~porcupine.tabs.FileTab.TabSettingChanged:foo`,
where ``foo`` is the name of the setting.

.. autofunction:: use_pygments_fg_and_bg


Functions for global settings
-----------------------------

These functions work with global settings only.
They are not available for other :class:`Settings` instances.

.. autofunction:: show_dialog
.. autofunction:: save
