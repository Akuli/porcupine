File Types
==========

Porcupine supports editing several different kinds of files. This page is all
about customizing its behaviour for each file type.


filetypes.ini
-------------

This file contains a bunch of filetype-specific settings. Porcupine's
default settings should be good enough for most things, but this file
lets you customize everything.

.. TODO: add a handy menu button that opens the file

For example, Porcupine uses 4 spaces for indenting with C by default and
the long line marker is disabled. You can configure Porcupine to use
`the Linux coding style <https://www.kernel.org/doc/html/v4.10/process/coding-style.html>`_
instead by adding this to ``filetypes.ini``:

.. TODO: add a menu for choosing the filetype that displays the name
   (which is the same name as in [] here

.. code-block:: ini

    [C]
    tabs2spaces = no
    indent_size = 8
    max_line_length = 80

Here's more detailed documentation about the valid options:

tabs2spaces
    Set this to ``yes`` if pressing the Tab key should produce spaces
    instead of tab characters.

indent_size
    The number of spaces used for indentation, or the width of one tab.
    This must be a positive integer.

max_line_length
    Recommended maximum line length, in characters. Set this to 0 for no
    line length limit. This must be a non-negative integer.

.. TODO: allow arbitary commands, maybe command.Compile or something

compile_command
run_command
lint_command
    Command strings that are used for compiling, running and
    checking the files, respectively. Each of these can also be
    empty for no command at all. The commands are always executed in the
    directory that the file is in.

    The following substitutions are performed. Use ``{{`` and ``}}``
    if you want to include literal brace characters.

    ``{file}``
        Name of the source file with an extension relative to its
        directory, quoted appropriately depending on the operating
        system. For example, ``test.c`` or ``"hello world.txt"``.

    ``{no_ext}``
        Like ``{file}``, but with the extension removed using
        :func:`os.path.splitext`. For example, ``test`` or
        ``"hello world"``. Leading dots aren't treated as file
        extensions, so ``.hidden.txt`` is turned into ``.hidden``.

    ``{no_exts}``
        Like ``{no_ext}``, but with consecutive extensions removed.
        For example, if ``{file}`` is ``stuff.tar.gz``, this is
        ``stuff``. As with ``{no_ext}``, leading dots don't count.

If the file contains invalid values, Porcupine will ignore the whole
file on startup but it will log a warning. The easiest way to see it is
to run Porcupine from a command prompt or terminal. Here's a command for
Windows command prompt:

.. code-block:: none

    py -m porcupine

And here's the equivalent terminal command for Mac OSX and Linux:

.. code-block:: none

    python3 -m porcupine

.. TODO: document filetypes.py here next
