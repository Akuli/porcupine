Getting porcupine to work with a programming language
=====================================================

People often ask whether Porcupine supports language X.
This file lists all the things that you may want to do for using Porcupine with a programming language.

.. note::
    Feel free to `create an issue on GitHub <https://github.com/Akuli/porcupine/issues/new>`_
    if you get any issues when following this guide.


How to edit filetypes.ini
-------------------------

Click the *Edit* menu and choose *Porcupine Settings*.
Then go to the *File Types* tab and click *Edit filetypes.ini*.
This opens Porcupine's filetype configuration file.

If you don't see programming language X listed, then
make a copy of the configuration for the configuration for some other programming language, and adjust it to your liking.
Save the configuration file and restart Porcupine.

Many of the settings are quite obvious, such as ``indent_size`` and ``tabs2spaces``.
Rest of this page explains less obvious settings.


Detecting the correct file type
-------------------------------

Python files are usually named ``something.py``, so ``filetypes.ini`` has this in the Python section::

    filename_patterns = *.py

Do something similar for the section of programming language X if needed.

You can also specify more than one pattern by separating them with spaces.
For example, C code is usually in files named ``something.h`` and ``something.c``,
so this configuration could be useful for C::

    filename_patterns = *.c *.h

Porcupine also supports specifying ``mimetypes`` instead of ``filename_patterns``.
Ignore that if you don't know what MIME types are.

Sometimes files are named without the file extension, as in just ``foo`` instead of ``foo.py``,
but they instead have a shebang such as ``#!/usr/bin/env python3`` on the first line.
Porcupine supports that by letting you specify ``shebang_regex``.
For example, this line is in the default Python configuration::

    shebang_regex = python(\\d(\\.\\d)?)?$

This matches any files whose first line ends with either ``python``, ``pythonX`` or ``pythonX.Y``,
where ``X`` and ``Y`` are digits.

The shebang must be on the first line of the file with no indentation in front,
and that first line must start with ``#!``.
This is the way shebangs work, and not an arbitrary Porcupine limitation.


Syntax highlighting
-------------------

Try opening a file written in programming language X.
If it syntax highlights correctly, you can skip rest of this section.

There is `a list of supported languages <https://pygments.org/docs/lexers/>`_ in Pygments documentation.
Pygments is the library that Porcupine uses for syntax highlighting.
For example, if you want to use ``pygments.lexers.zig.ZigLexer`` from the above link, add this to the filetype config::

    pygments_lexer = pygments.lexers.zig.ZigLexer

If your language is not supported by Pygments, it might be still possible to get highlighting for it.
Try to search for a Pygments lexer for that language.
If you find one, put it somewhere where Porcupine's Python can import it (TODO: explain in more detail),
let's say ``class LexerClass`` in file ``lexer_filename.py``.
Then you can add this to ``filetypes.ini``::

    pygments_lexer = lexer_filename.LexerClass


Autocompletions with langserver
-------------------------------

Porcupine's autocompletions work with a langserver.
It's a program that runs on your computer and doesn't use the internet at all,
unlike you might guess from the name.
Porcupine requests completions from the langserver and displays them to you.

Start by finding and installing a langserver for the programming language X.
I don't have any more detailed instructions, because this depends a lot on which programming language is in question.

When the langserver is installed, you should be able to invoke it from the terminal or command prompt with some command.
For example, typing ``pyls`` on the terminal starts the Python language server that I use,
so I have this in my Python configuration in ``filetypes.ini``::

    langserver_command = pyls
    langserver_language_id = python

Set ``langserver_command`` to whatever command you want.
To find the correct ``langserver_language_id``, click
`this link <https://microsoft.github.io/language-server-protocol/specifications/specification-current/#textDocumentItem>`_
and scroll down a bit.
You should find a table of all valid ``langserver_language_id`` values.

Many langservers have an option for whether to use stdio (also known as stdin and stdout) or a TCP socket.
Choose stdio.

Currently Porcupine doesn't support langservers with TCP sockets at all,
but if the langserver doesn't support stdio and you need to use it with a TCP socket,
you can use ``netcat`` to get it to work anyway.
Add this to the filetype configuration::

    langserver_command = nc localhost 1234

Replace ``1234`` with whatever port the langserver process uses.
If your system doesn't have netcat (also known as ``nc``), then install it,
and if needed, replace ``nc`` with whatever command is needed for running netcat.
Now run the langserver in another terminal before opening any files that need the langserver.


Notes
-----

If your ``filetypes.ini`` contains something invalid, Porcupine will print a
warning message to the terminal or command prompt and start normally.
To run porcupine from Windows command prompt, use ``py -m porcupine``.
On other operating systems, run ``python3 -m porcupine`` on a terminal.
Everything printed to the terminal also goes to Porcupine's log file, even when Porcupine is not started from a terminal.
(TODO: explain where log files are)

If you want to reset all changes you have done to your ``filetypes.ini``, just delete it
and restart Porcupine. It will create a new ``filetypes.ini``.

Porcupine can often get syntax highlighting to work without any configuration in ``filetypes.ini``.
In those cases, Porcupine adds `` (not from filetypes.ini)`` to the filetype name shown in the statusbar.
You may still want to add some indentation settings and such to ``filetypes.ini``.


The ``porcupine.filetypes`` module
----------------------------------

.. module:: porcupine.filetypes

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
    ============================    ========================================

    If no ``shebang_regex`` is given in ``filetypes.ini``, ``shebang_regex`` is
    set to a regex object that matches nothing.

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
