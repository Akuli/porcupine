:mod:`porcupine.filetypes` --- low-level access to ``filetypes.toml`` stuff
===========================================================================

.. module:: porcupine.filetypes

.. note::
    Consider using :attr:`porcupine.tabs.FileTab.settings` instead of :mod:`porcupine.filetypes`.
    The ``settings`` object provides a type-safe way to access filetype-specific settings,
    while the filetypes are just one way how filetype-specific settings get loaded.

.. seealso::
    The documentation for configuring ``filetypes.toml`` is in
    `Porcupine Wiki <https://github.com/Akuli/porcupine/wiki/Getting-Porcupine-to-work-with-a-programming-language>`_.

Each filetype is identified by a name,
which is the string between ``[`` and ``]`` in the ``.toml`` files.
Filetypes are represented as dicts with :class:`str` keys and any objects as values,
corresponding to whatever is specified in the ``.toml`` files.

When functions in :mod:`porcupine.filetypes` return filetype dicts,
there's no ``filename_patterns`` or ``shebang_regex`` in those dicts,
because those are used to look up the correct filetype
and shouldn't be used for anything else.

.. autofunction:: guess_filetype
.. autofunction:: get_filetype_by_name
.. autofunction:: get_filetype_names
.. autofunction:: get_filedialog_kwargs
