:mod:`porcupine.filetypes` --- ``filetypes.ini`` stuff
======================================================

.. module:: porcupine.filetypes

.. seealso::
    The documentation for configuring ``filetypes.ini`` is in
    `Porcupine Wiki <https://github.com/Akuli/porcupine/wiki/Getting-Porcupine-to-work-with-a-programming-language>`_.



This module exposes an API for things that are defined in ``filetypes.ini``.


.. _filetype-objects:

Filetype Objects
^^^^^^^^^^^^^^^^

Many functions in :mod:`porcupine.filetypes` return filetype objects. Most
filetype objects represent the configuration for one file type in ``filetypes.ini``,
but Porcupine creates new filetype objects on the fly for files that Pygments knows but ``filetypes.ini`` doesn't.

Filetype objects have these attributes and methods:

.. attribute:: somefiletype.name

    This is ``[the text in square brackets]`` in ``filetypes.ini``, intended to
    be human-readable.

    Names of filetypes that were created "on the fly" as opposed to loading
    from ``filetypes.ini`` end with ``' (not from filetypes.ini)'``.

.. attribute:: somefiletype.filename_patterns
.. attribute:: somefiletype.mimetypes
.. attribute:: somefiletype.shebang_regex
.. attribute:: somefiletype.tabs2spaces
.. attribute:: somefiletype.indent_size
.. attribute:: somefiletype.max_line_length
.. attribute:: somefiletype.langserver_command
.. attribute:: somefiletype.langserver_language_id
.. attribute:: somefiletype.langserver_port

    See your ``filetype.ini`` for details regarding each attribute. Types or
    possible values are listed here:

    ============================    ========================================
    ``filename_patterns``           list of strings
    ``mimetypes``                   list of strings
    ``shebang_regex``               a regex object from :func:`re.compile`
    ``tabs2spaces``                 True or False
    ``indent_size``                 int
    ``max_line_length``             int
    ``langserver_command``          str
    ``langserver_language_id``      str
    ``langserver_port``             int or None
    ============================    ========================================

    If no ``shebang_regex`` is given in ``filetypes.ini``, ``shebang_regex`` is
    set to a regex object that matches nothing.

    Setting ``langserver_port`` to None means that stdin and stdout of the
    langserver process will be used instead of a TCP socket.

.. method:: somefiletype.get_lexer(**kwargs)

    Return a suitable `Pygments lexer <http://pygments.org/docs/api/#lexers>`_.

    Keyword arguments are passed to the lexer class.

.. method:: somefiletype.get_command(something_command, basename)

    Return a list of a program and arguments for compiling, running or linting
    a file.

    The returned list is compatible with e.g. the :mod:`subprocess` module.

    *something_command* argument must be ``'compile_command'``,
    ``'run_command'`` or ``'lint_command'``, and *basename* should be a path to
    the file as a string relative to the file's location. For example, the
    *basename* of ``'/home/akuli/test.py'`` is ``'test.py'``, but the command
    returned by this method should be ran in ``/home/akuli/``.

.. method:: somefiletype.has_command(something_command)

    Return True if the given command option was set to something else than an
    empty string and ``somefiletype.get_command(something_command, some_path)``
    will return a useful value.


Functions
^^^^^^^^^

.. autofunction:: guess_filetype
.. autofunction:: get_filetype_by_name
.. autofunction:: get_all_filetypes
.. autofunction:: get_filedialog_kwargs
