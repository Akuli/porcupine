:mod:`porcupine.pluginloader` --- The module that loads plugins on startup
==========================================================================

.. module:: porcupine.pluginloader

On startup, Porcupine loads plugins roughly like this (after calling
:func:`porcupine.init`)::

    from porcupine import pluginloader
    pluginloader.load_plugins(pluginloader.find_plugins())

:source:`The real code <porcupine/__main__.py>` is a little more complicated
than that because the behaviour can be changed with command-line arguments, but
you get the idea.

In this documentation, a plugin name means no file extension or
``porcupine.plugins.`` prefix, e.g. ``highlight`` instead of ``highlight.py``
or ``porcupine.plugins.highlight``.

.. autofunction:: find_plugins
.. autofunction:: load
.. autofunction:: get_loaded_plugins
