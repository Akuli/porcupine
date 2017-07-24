:mod:`porcupine.utils` --- Handy utility functions and classes
==============================================================

.. module:: porcupine.utils

This module contains handy things that Porcupine uses internally and
plugins can use freely.

Callback Hook Classes
---------------------

These classes are used for running callbacks in Porcupine:

.. autoclass:: CallbackHook
    :members:

    .. attribute:: callbacks

        A list of the connected functions. This is useful for things
        like checking if something is connected::

            >>> hook = CallbackHook('whatever')
            >>> hook.connect(print)
            >>> hook.callbacks == [print]
            True

.. autoclass:: ContextManagerHook

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

.. autoclass:: Checkbox
.. autofunction:: get_window
.. autofunction:: get_root
.. autofunction:: copy_bindings
.. autofunction:: bind_mouse_wheel
.. autofunction:: run_in_thread
.. autofunction:: get_image
.. autofunction:: errordialog

Miscellaneous
-------------

.. autofunction:: backup_open
.. autofunction:: invert_color
