File Types
==========

.. _automagic-filetype-creation:

Porcupine supports editing several different kinds of files. When opening or
saving a file, only a small subset of supported file types is listed under the
"Files of type" menu, so if the type of some file is not listed there just
select "All Files". There's a good chance that your file will be syntax
highlighted correctly anyway.


filetypes.ini
-------------

If you edit files of some specific type often, you can add that file type to
your ``filetypes.ini`` configuration file. This way it will show up on the
"Files of type" menu, but you can also set up other stuff such as indentation
settings or running commands.

.. note::
    Currently the compiling, running and linting commands specified in
    ``filetypes.ini`` don't actually do anything. I'll update
    :source:`porcupine/plugins/run` to support them some day.

Porcupine creates a ``filetypes.ini`` when it's started for the first time. By
default, it contains instructions for editing the file as comments and the
default settings that Porcupine is using.

An easy way to edit ``filetypes.ini`` is to open *Porcupine Settings* from the
*Edit* menu and click the *Edit filetypes.ini* button. Then follow the
instructions in the beginning of the file.

If your ``filetypes.ini`` contains something invalid, Porcupine will print a
warning message to the terminal or command prompt and start normally.
(Currently seeing the message requires using ``porcu --verbose``, but hopefully
I'll fix that some day). If you want to reset all changes you have done to
``filetypes.ini``, just delete it and restart Porcupine to create a new
``filetypes.ini``.


The ``porcupine.filetypes`` module
----------------------------------

.. module:: porcupine.filetypes

This module exposes an API for things that are defined in ``filetypes.ini``.


.. _filetype-objects:

Filetype Objects
^^^^^^^^^^^^^^^^

Many functions in :mod:`porcupine.filetypes` return filetype objects. Most
filetype objects represent a section beginning with ``[a header]`` in
``filetypes.ini``, but Porcupine creates new filetype objects on the fly as
needed (see :ref:`above <automagic-filetype-creation>`).

Filetype objects have these attributes and methods:

.. attribute:: somefiletype.name

    This is ``[the text in square brackets]`` in ``filetypes.ini``, intended to
    be human-readable.

    Names of filetypes that were created "on the fly" as opposed to loading
    from ``filetypes.ini`` end with ``' (not from filetypes.ini)'``.

.. attribute:: somefiletype.filename_patterns
.. attribute:: somefiletype.mimetypes
.. attribute:: somefiletype.tabs2spaces
.. attribute:: somefiletype.indent_size
.. attribute:: somefiletype.max_line_length

    See your ``filetype.ini`` for details regarding each attribute. Types or
    possible values are listed here:

    ========================    ====================
    ``filename_patterns``       list of strings
    ``mimetypes``               list of strings
    ``tabs2spaces``             True or False
    ``indent_size``             int
    ``max_line_length``         int
    ========================    ====================

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
