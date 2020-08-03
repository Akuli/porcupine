:mod:`porcupine.textwidget` --- Handy ``tkinter.Text`` subclasses
=================================================================

.. module:: porcupine.textwidget

This module contains handy ``tkinter.Text`` subclasses.

.. this specifes a list of the members because overrided @functools.wraps
   methods also like to show up, but we want to hide them

.. autoclass:: HandyText
   :members: iter_chunks, iter_lines

.. autoclass:: ThemedText
   :members: set_colors

.. no members, the docstring says "dont use this"
.. autoclass:: MainText


Change Information
------------------

Use :virtevt:`HandyText.ContentChanged` to run a callback when the content of
the text widget changes. These classes describe what changed:

.. autoclass:: Change

    This :mod:`dataclass <dataclasses>` represents any change in the text widget,
    where ``old_text_len`` characters between the text widget indexes ``start``
    and ``end`` get replaced with ``new_text``. For example, this...
    ::

        # let's say that text widget contains 'hello world'
        textwidget.replace('1.0', '1.5', 'toot')

    \...changes the ``'hello'`` to ``'toot'``, and that's represented by a
    ``Change`` like this::

        Change(start='1.0', end='1.5', old_text_len=5, new_text='toot')

    Insertions are represented with ``Change`` objects having ``old_text_len=0``
    and the same ``start`` and ``end``. For example,
    ``textwidget.insert('1.0', 'hello')`` corresponds to this ``Change``::

        Change(start='1.0', end='1.0', old_text_len=0, new_text='hello')

    For deletions, ``start`` and ``end`` differ and ``new_text`` is empty.
    If the first line of a text widget contains at least 5 characters, then
    deleting the first 5 characters looks like this::

        Change(start='1.0', end='1.5', old_text_len=5, new_text='')

    Unlike you might think, the ``old_text_len`` is not redundant. Let's
    say that the text widget contains ``'toot world'`` and all that is
    deleted::

        Changes(change_list=[
            Change(start='1.0', end='1.10', old_text_len=10, new_text=''),
        ])

    After the deletion, ``'1.10'`` is no longer a valid index in the text
    widget because it contains 0 characters (and 0 is less than 10).
    In this case, checking only the ``0`` of ``1.0`` and the ``10`` of ``1.10``
    could be used to calculate the 10,
    but that doesn't work right when changing multiple lines.

.. autoclass:: Changes

    This :mod:`dataclass <dataclasses>` represents a list of several
    :class:`Change`\ s applied at once.
    The ``change_list`` is always ordered so that most recent change is
    ``change_list[-1]`` and the oldest change is ``change_list[0]``.

    This boilerplate class is needed instead of a plain ``List[Change]``
    because of how :class:`porcupine.utils.EventDataclass` works.
