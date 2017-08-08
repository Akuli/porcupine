:mod:`porcupine` --- The top level Porcupine package
====================================================

.. module:: porcupine

Doing ``import porcupine`` gives you access to the things documented here. It
*may* work for other submodules too, but it's recommended to be more specific
when importing them, like ``from porcupine import tabs``.


Stuff that the intro covers too
-------------------------------

If you haven't read :ref:`the plugin writing introduction <plugin-intro>` yet
I recommend reading it first. Then you'll have a much better idea about what
these functions do.

.. autofunction:: get_main_window
.. autofunction:: get_tab_manager
.. autofunction:: add_action


Really high-level file API
--------------------------

These functions create :class:`FileTab <porcupine.tabs.FileTab>` objects
and add them to the tab manager.

.. warning::
   I may remove these functions later because they really don't do much (see
   the [source] links at right). Use :class:`porcupine.tabs.FileTab` directly
   instead of these functions.

.. autofunction:: porcupine.new_file
.. autofunction:: porcupine.open_file


Session stuff
-------------

.. autofunction:: porcupine.quit
.. autofunction:: porcupine.init


Version Information
-------------------

.. data:: version_info
.. data:: __version__

   These variables contains information about the current Porcupine version.
   ``version_info`` is a tuple like ``(0, 28, 1)``, and ``__version__`` is a
   string such as ``'0.28.1'``. Use ``version_info`` for checking if Porcupine
   supports a specific feature::

      if porcupine.version_info >= (0, 28):
          # use some feature that was added in Porcupine 0.28
      else:
          # display an error message or do things without the new feature
