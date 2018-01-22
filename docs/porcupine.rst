:mod:`porcupine` --- The top level Porcupine package
====================================================

.. module:: porcupine

Doing ``import porcupine`` gives you access to the things documented here. It
*may* work for other submodules too, but it's recommended to be more specific
when importing them, like ``from porcupine import tabs``.


Basic Stuff
-----------

If you haven't read :ref:`the plugin writing introduction <plugin-intro>` yet
I recommend reading it first. Then you'll have a much better idea about what
these functions do.

.. autofunction:: get_main_window
.. autofunction:: get_tab_manager


Running Porcupine from Python
-----------------------------

When Porcupine is started normally, it's roughly equivalent to running a script
like this in Python::

    import porcupine
    from porcupine import pluginloader

    porcupine.init()
    pluginloader.load(pluginloader.find_plugins())
    porcupine.run()

This is useful for implementing plugins that need to start a new Porcupine
process.

See :mod:`porcupine.pluginloader` documentation for more about loading plugins.
Note that the plugins assume that :func:`porcupine.init` has been called, so
they must be loaded after calling :func:`init`.

.. autofunction:: init
.. autofunction:: run
.. autofunction:: quit


Version Information
-------------------

.. data:: version_info
.. data:: __version__

   These variables contains information about the current Porcupine version.
   ``version_info`` is a tuple like ``(0, 28, 1)``, and ``__version__`` is a
   string such as ``'0.28.1'``. Use ``version_info`` for checking if Porcupine
   supports a specific feature::

      if porcupine.version_info >= (0, 28):
          # use some feature that was added in Porcupine 0.28
      else:
          # display an error message or do things without the new feature
