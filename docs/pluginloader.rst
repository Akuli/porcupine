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
    Don't modify this sequence outside ``porcupine/pluginloader.py``.

.. virtualevent:: PluginsLoaded

    This virtual event is generated once on the main window
    when the ``setup()`` methods of all plugins have been called on startup.
    Bind to it if you want to run things that must not happen
    until plugins are ready for it.

    .. seealso:: :func:`porcupine.get_main_window`

    Note that it's possible to setup plugins individually while Porcupine is running.
    This event also runs after that happens.

    .. seealso:: :func:`setup_while_running`

.. autofunction:: can_setup_while_running
.. autofunction:: setup_while_running

.. note::
    The functions documented above handle the errors coming from plugins,
    so there's no need to use ``try/except`` when calling them.
