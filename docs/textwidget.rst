:mod:`porcupine.textwidget` --- Handy ``tkinter.Text`` subclasses
=================================================================

.. module:: porcupine.textwidget

This module contains handy ``tkinter.Text`` subclasses.

.. this specifes a list of the members because overrided @functools.wraps
   methods also like to show up, but we want to hide them

.. autoclass:: HandyText
   :members: cursor_has_moved, iter_chunks, iter_lines

.. autoclass:: ThemedText
   :members:

.. no members, the docstring says "dont use this"
.. autoclass:: MainText
