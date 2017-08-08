:mod:`porcupine.settings` --- Porcupine's setting manager
=========================================================

.. module:: porcupine.settings

This module managers Porcupine's settings.

.. warning::
   Don't use this module in plugins. I'll probably change how the settings
   work later. This module is documented here just because Porcupine's code
   uses it and you might be reading it.


The config
----------

The ``config`` variable is set to an object that behaves like a
``{(section, configkey): value}`` dictionary where *section* and
*configkey* are strings. The config object also support things like
default values and running callbacks when something changes. Note that
``config['section', 'key']`` does the same thing as
``config[('section', 'key')]``, so usually you don't need to use
parentheses when setting or getting values.

.. note::
   If you use threads, don't set config values from other threads
   than the main thread. Setting values may run callbacks that need
   to do something with tkinter.

Currently the config contains these keys:

   ``config['Font', 'family']`` and ``config['Font', 'size']``
      The current font family and size as an integer and a string,
      respectively.

      Porcupine also keeps the current font in a special font named
      ``TkFixedFont`` that ``Text`` widgets use by default. If you need to
      access these config values it's easiest to just use that::

         import tkinter.font as tkfont

         fixedfont = tkfont.Font(name='TkFixedFont', exists=True)

   ``config['Files', 'encoding']``
      This is a string that should be like
      ``open(..., encoding=config['Files', 'encoding'])`` when opening a file
      for editing.

   ``config['Files', 'add_trailing_newline']``
      If this boolean is True, Porcupine makes sure that each file ends with a
      newline before saving.

      This really should be a plugin, not a config option.

   ``config['Editing', 'pygments_style']``
      Name of a Pygments style, not the style object itself.

      Use this config value like this::

         from porcupine.settings import config
         import pygments.styles

         the_style = pygments.styles.get_style_by_name(config['Editing', 'pygments_style'])

   ``config['GUI', 'default_size']``
      The default size of the main window as a Tk geometry string,
      e.g. ``'300x400'``.


Adding More Keys
^^^^^^^^^^^^^^^^

Unlike with dictionaries, you need to add keys to the config
before you can set them to a value. The config also keeps track of default
values for you and lets you specify functions that check new values.

..  documenting methods from an instance like this seems to work,
    i'll fix this if this breaks in a newer sphinx

.. automethod:: porcupine.settings.config.add_key
.. automethod:: porcupine.settings.config.add_bool_key
.. automethod:: porcupine.settings.config.add_int_key


Running Callbacks
^^^^^^^^^^^^^^^^^

.. automethod:: porcupine.settings.config.connect
.. automethod:: porcupine.settings.config.disconnect


Other things
^^^^^^^^^^^^

.. automethod:: porcupine.settings.config.reset
.. autoexception:: porcupine.settings.InvalidValue
