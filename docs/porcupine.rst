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
:func:`get_main_window` and :func:`get_tab_manager` do.

.. autofunction:: get_main_window
.. autofunction:: get_tab_manager
.. autofunction:: get_parsed_args
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


File Dialogs
------------

.. data:: filedialog_kwargs
    :type: Dict[str, Any]

    Porcupine uses :mod:`tkinter.filedialog` functions similarly to this::

        path = filedialog.asksaveasfilename(**porcupine.filedialog_kwargs)

    The :source:`filetypes plugin <porcupine/plugins/filetypes.py>` uses this
    for displaying known filetypes in the dialogs.


Directories
-----------

.. data:: dirs
    :type: appdirs.AppDirs

    See `appdirs on PyPI <https://pypi.org/project/appdirs/>`_.
    For example, ``porcupine.dirs.user_cache_dir`` is where temporary cache files should go.

    When Porcupine starts, it makes sure that these directories exist:

        * ``dirs.user_cache_dir``
        * ``dirs.user_config_dir`` and a subdirectory named ``plugins`` inside it
        * ``dirs.user_log_dir``
