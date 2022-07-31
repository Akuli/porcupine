:mod:`porcupine.utils` --- Handy utility functions and classes
==============================================================

.. module:: porcupine.utils

This module contains handy things that Porcupine uses internally and
plugins can use freely.


Information about Python
------------------------

.. data:: running_pythonw

    This is True if Python is running in pythonw.exe on Windows.

    The ``pythonw.exe`` program runs Python scripts without a command
    prompt, so you need to check for that when doing things like
    starting a new command prompt from Python. This is also ``True``
    if Porcupine is running as ``Porcupine.exe``, which it is when
    launched from start menu.

.. data:: python_executable

   Like :data:`sys.executable`, but this should also be correct on
   ``pythonw.exe``.


Events with Data
----------------

.. autofunction:: bind_with_data
.. autoclass:: EventWithData
    :members:
.. autoclass:: EventDataclass


Other Tkinter Utilities
-----------------------

.. seealso:: :mod:`porcupine.textutils` contains ``tkinter.Text`` specific things.

.. autofunction:: bind_tab_key
.. autofunction:: add_scroll_command
.. autofunction:: run_in_thread
.. autoclass:: PanedWindow


Miscellaneous
-------------

.. autofunction:: invert_color
.. autofunction:: mix_colors
.. autofunction:: backup_open
.. autofunction:: find_project_root

.. function:: quote(argument)

   Add quotes around an argument of a command.

   This function is equivalent to :func:`shlex.quote` on non-Windows systems,
   and on Windows it adds double quotes in a similar way. This is useful for
   running commands in the Windows command prompt or a POSIX-compatible shell.
