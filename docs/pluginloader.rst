:mod:`porcupine.pluginloader` --- The module that loads plugins on startup
==========================================================================

.. module:: porcupine.pluginloader

On startup, Porcupine loads plugins roughly like this (after calling
:func:`porcupine.init`)::

    from porcupine import pluginloader
    pluginloader.load()

:source:`The real code <porcupine/__main__.py>` is a little more complicated
than that because the behaviour can be changed with command-line arguments, but
you get the idea.

In this documentation, a plugin name means no file extension or
``porcupine.plugins.`` prefix, e.g. ``highlight`` instead of ``highlight.py``
or ``porcupine.plugins.highlight``.

.. autoclass:: Status
.. autoclass:: PluginInfo

.. data:: plugin_infos
    :type: Sequence[PluginInfo]

    This contains infos for all the plugins that the plugin loader knows about,
    including plugins that failed to load and disabled plugins.

.. autofunction:: load

.. virtualevent:: PluginsLoaded

    This virtual event is generated on the main window
    when the ``setup()`` methods of all plugins have been called.
    Bind to it if you want to run things that must not happen
    until plugins are ready for it.

    .. seealso:: :func:`porcupine.get_main_window`
