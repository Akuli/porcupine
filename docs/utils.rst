:mod:`porcupine.utils` --- Handy utility functions and classes
==============================================================

.. module:: porcupine.utils

This module contains handy things that Porcupine uses internally and
plugins can use freely.

.. TODO: document the img_stuff API


Information about Python
------------------------

.. data:: running_pythonw

    This is True if Python is running in pythonw.exe on Windows.

    The ``pythonw.exe`` program runs Python scripts without a command
    prompt, so you need to check for that when doing things like
    starting a new command prompt from Python.

.. data:: python_executable

   Like :data:`sys.executable`, but this should also be correct on
   ``pythonw.exe``.


Tkinter Utilities
-----------------

.. autofunction:: set_tooltip
.. autofunction:: bind_mouse_wheel
.. autofunction:: bind_tab_key
.. autofunction:: bind_with_data
.. autofunction:: run_in_thread
.. autoclass:: TemporaryBind

.. class:: Spinbox

   Starting with Python 3.7, this is ``tkinter.ttk.Spinbox``. On Python 3.6,
   this class behaves just like ``tkinter.ttk.Spinbox`` on Python 3.7.


Miscellaneous
-------------

.. autofunction:: invert_color
.. autofunction:: backup_open

.. function:: quote(argument)

   Add quotes around an argument of a command.

   This function is equivalent to :func:`shlex.quote` on non-Windows systems,
   and on Windows it adds double quotes in a similar way. This is useful for
   running commands in the Windows command prompt or a POSIX-compatible shell.

.. autofunction:: errordialog
