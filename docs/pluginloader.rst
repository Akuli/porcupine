:mod:`porcupine.pluginloader` --- The module that loads plugins on startup
==========================================================================

.. module:: porcupine.pluginloader

In this documentation, a plugin name means no file extension or
``porcupine.plugins.`` prefix, e.g. ``highlight`` instead of ``highlight.py``
or ``porcupine.plugins.highlight``.

.. autoclass:: Status
.. autoclass:: PluginInfo

.. data:: plugin_infos
    :type: Sequence[PluginInfo]

    This contains infos for all the plugins that the plugin loader knows about,
    including plugins that failed to load and disabled plugins.

.. virtualevent:: PluginsLoaded

    This virtual event is generated on the main window
    when the ``setup()`` methods of all plugins have been called.
    Bind to it if you want to run things that must not happen
    until plugins are ready for it.

    .. seealso:: :func:`porcupine.get_main_window`

.. autofunction:: can_setup_while_running
.. autofunction:: setup_while_running
