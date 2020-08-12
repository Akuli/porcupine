:mod:`porcupine.settings` --- Porcupine's setting manager
=========================================================

.. module:: porcupine.settings

This module manages Porcupine's settings and the *Porcupine Settings* dialog
in the *Edit* menu.

.. |triangle| image:: ../porcupine/images/triangle.gif


Getting and Setting
-------------------

Use these functions for setting and getting values of options:

.. autofunction:: set
.. autofunction:: get
.. autofunction:: debug_dump

.. |br| raw:: html

    <br />

Porcupine has these options by default (but you can add your own options too, see below):

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

    ``default_filetype``: :class:`str`
        Name of the filetype used when a new file is created with e.g. Ctrl+N.

        .. seealso:: :meth:`porcupine.filetypes.get_filetype_by_name`

    ``disabled_plugins``: List[:class:`str`]

        Names of plugins that the user has disabled. See :mod:`porcupine.pluginloader`.


Custom Options
--------------

You can use :mod:`porcupine.settings` for storing things that shouldn't reset every
time Porcupine is restarted.

.. autofunction:: add_option

Example::

    import logging
    from typing import Tuple
    from porcupine import settings

    log = logging.getLogger(__name__)

    def connect_to_http_server() -> None:
        host = settings.get('http_server_host', str)
        port = settings.get('http_server_port', int)
        log.info(f"Connecting to localhost:{port}...")
        ...

    def setup() -> None:
        # 80 and '127.0.0.1' are default values
        settings.add_option('http_server_host', '127.0.0.1')
        settings.add_option('http_server_port', 80)

All plugins use the same options, so don't make the option names too short.
For example, if two plugins define an option named ``port``,
then one of them will get an error from :func:`add_option` when the plugins get set up.
If the plugins had instead named their options e.g. ``langserver_port`` and ``http_server_port``,
then there would be no problem.

.. note::
    Porcupine stores the settings in a JSON file, but that file isn't meant to be
    edited directly by users. Instead, please provide some way to change the
    settings with a GUI, such as a handle that can be dragged to change the size
    settings of a widget, or add something to the setting dialog (see below).


The Settings Dialog
-------------------

Click *Porcupine Settings* in the *Edit* menu to open the dialog.
The dialog contains a :class:`tkinter.ttk.Notebook` widget and some buttons.

.. autofunction:: get_notebook

You can add widgets to the notebook yourself, but it's usually easiest to use this:

.. autofunction:: add_section

You can add widgets to the section yourself or use the following functions.
All of these assume that the *section* argument comes from :func:`add_section`
and return the added widget.
A label that displays *text* is added to column 0 (see the ascii art above).

.. autofunction:: add_entry
.. autofunction:: add_combobox
.. autofunction:: add_spinbox


Change Events
-------------

.. virtualevent:: SettingChanged:foo

    When any setting is changed,
    all widgets in the main window (see :func:`porcupine.get_main_window`)
    receive a virtual event named ``<<SettingChanged:option_name>>``,
    where ``option_name`` is the name of the changed setting.
    For example, ``<<SettingChanged:pygments_style>>`` runs
    when the user changes the Pygments style.

All widget bindings go away automatically when the corresponding widget is destroyed.
For example, if you want to update the configuration of a :class:`tkinter.Text` widget when ``pygments_style`` changes,
you should use the ``.bind()`` method of that text widget.
This way your callback won't be called when the text widget doesn't exist anymore.

If you want your binding to work as long as Porcupine is running,
use the bind method of :func:`porcupine.get_tab_manager`.

.. note::
    Don't use :func:`porcupine.get_main_window` for binding to ``<<SettingChanged:foo>>``.
    The main window is a :class:`tkinter.Tk` or :class:`tkinter.Toplevel` widget,
    so it gets notified of its child widgets' events too.
    For example, let's say that  there are 100 widgets currently being shown in the main window,
    and you unwisely use the main window's ``bind()`` to bind ``<<SettingChanged:foo>>``.
    When the ``foo`` setting changes, your bind callback runs
    100 times with ``event.widget`` set to something else than the main window, and
    once with ``event.widget`` set to the main window.
    This can cause annoying slowness.


Misc functions
--------------

.. autofunction:: reset
.. autofunction:: reset_all
.. autofunction:: show_dialog
.. autofunction:: save


Non-global Settings
-------------------

.. class:: Settings

    This class provides settings that behave a lot like the global settings described above,
    but each instance of :class:`Settings` has its own options
    and isn't related to other instances or global settings.
    See :class:`porcupine.tabs.Tab.settings` for an example.

    The change events of :class:`Settings` instances differ from :virtevt:`SettingChanged:foo`:

        * The change events are named differently.
        * Instead of having all child widgets of the main window receive the virtual events,
          only one widget receives them.

    The name of the event and the receiving widget should be mentioned
    in the documentation of the :class:`Settings` instance,
    such as the documentation of an attribute with type :class:`Settings`.

    .. method:: set(option_name, value)
    .. method:: get(option_name, tybe)
    .. method:: add_option(option_name, default)
    .. method:: debug_dump()

        These methods are just like the
        :func:`set`, :func:`get`, :func:`add_option` and :func:`debug_dump` functions,
        but they do things with the :class:`Settings` instance, not with the global settings.
