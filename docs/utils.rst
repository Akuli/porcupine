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
    starting a new command prompt from Python.

.. data:: python_executable

   Like :data:`sys.executable`, but this should also be correct on
   ``pythonw.exe``.

.. data:: short_python_command

   A short command for running the Python that Porcupine is running on.

   This may contain arguments. For example, this might be ``'py -3'`` on a
   Windows system that has both Python 2 and Python 3 installed, and Python 2
   is the default.

   Note that this is quoted already if it needs quoting, and should *not* be
   quoted more. For example, this example is **bad**::

      subprocess.call([utils.short_python_command, 'blah', 'blah'])

   Use :data:`python_executable` if you want to do a :func:`subprocess.call` or
   something like that.


Tkinter Utilities
-----------------

.. autofunction:: bind_mouse_wheel
.. autofunction:: bind_tab_key
.. autofunction:: copy_bindings
.. autoclass:: Checkbox
.. autofunction:: run_in_thread
.. autofunction:: get_image


Miscellaneous
-------------

.. autofunction:: invert_color
.. autofunction:: backup_open

.. function:: quote(argument)

   Add quotes around an argument of a command.

   This function is equivalent to :func:`shlex.quote` on non-Windows systems,
   and on Windows it adds double quotes in a similar way. This is useful for
   running commands in the Windows command prompt or a POSIX-compatible shell.


Don't-use-this functions
------------------------

I might remove these functions later, and they are there because some part of
Porcupine still uses them, the function does something that was difficult to
implement or I'm planning on rewriting the whole function in an incompabile way
later.

.. autofunction:: errordialog
.. autofunction:: temporary_bind
