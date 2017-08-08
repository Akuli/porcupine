:mod:`porcupine.utils` --- Handy utility functions and classes
==============================================================

.. module:: porcupine.utils

This module contains handy things that Porcupine uses internally and
plugins can use freely.


Information about Python
------------------------

.. data:: running_pythonw

    This is True if Python is running in pythonw.exe on Windows.

    The pythonw.exe program runs Python scripts without a command
    prompt, so you need to check for that when doing things like
    starting a new command prompt from Python.

.. data:: python

    If :data:`.running_pythonw` is False, this is
    :data:`sys.executable`. This should point to the real python.exe
    when running in pythonw.exe.


Tkinter Utilities
-----------------

.. autofunction:: bind_mouse_wheel
.. autofunction:: bind_tab_key
.. autofunction:: copy_bindings
.. autoclass:: Checkbox
.. autofunction:: run_in_thread
.. autofunction:: get_image

.. function:: quote(argument)
   Add quotes around an argument of a command.

   This function is equivalent to :func:`shlex.quote` on non-Windows systems,
   and on Windows it adds double quotes in a similar way. This is useful for
   running commands in the Windows command prompt or a POSIX-compatible shell.


Miscellaneous
-------------

.. autofunction:: backup_open
.. autofunction:: invert_color


Don't-use-this functions
------------------------

I might remove these functions later, and they are there because some part of
Porcupine still uses them or these functions do something that was difficult
to implement.

.. autofunction:: errordialog
.. autofunction:: temporary_bind
.. autofunction:: nice_repr
