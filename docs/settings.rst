:mod:`porcupine.settings` --- Porcupine's setting manager
=========================================================

.. module:: porcupine.settings

This module manages Porcupine's settings and the *Porcupine Settings* dialog
in the *Edit* menu.

.. |triangle| image:: ../porcupine/images/triangle.gif


Getting Started
---------------

The settings are divided into **sections**. Each section is shown as
a tab in the setting dialog. You can also create your own sections.

.. autofunction:: get_section

For example, you can do this::

   from porcupine import settings

   general_config = settings.get_section('General')   # get an existing section
   wat_config = settings.get_section('Wat Wat')       # create a new section

Then you can do this::

   def read_some_file():
       with open(some_path, 'r', encoding=general_config['encoding']) as file:
           return file.read()

   wat_config.add_option('wat_on_startup', default=True)
   wat_config.add_checkbutton('wat_on_startup', "Do wat on startup")

   def setup():
       if wat_config['wat_on_startup']:
           print("Wat Wat!")

The sections behave a lot like dictionaries, so if you can do something with
a dict you can probably do it with a section object as well.

One restriction is that you can only use :mod:`json` compatible values,
like strings, integers, floats and bools. I don't recommend lists and dicts
because they're mutable; for example, after ``section['key'] = []``, the
:meth:`connect() <section.connect>` callbacks don't run if you do
``section['key'].append('wat')``.

The "General" section has these options by default (but you can add more, see
`Adding Options`_ below):

   ``encoding``
      This encoding should be used when reading and writing the user's files.
      The default value is ``'UTF-8'``.

   ``font_family`` and ``font_size``
      The current font family and size as a string and an integer.

      Porcupine also keeps these settings in a special font named
      ``TkFixedFont``, so if you want to use this font in a widget just
      pass it a ``font='TkFixedFont'`` option. ``Text`` widgets use
      ``TkFixedFont`` by default.

      Do this if you need a ``Font`` object instead of the font name as a
      string::

         import tkinter.font as tkfont

         fixedfont = tkfont.Font(name='TkFixedFont', exists=True)

   ``pygments_style``
      Name of the current Pygments style, not the style object itself.

      Use this config value like this::

         from porcupine import settings
         from pygments import styles

         general_config = settings.get_section('General')
         the_style = styles.get_style_by_name(general_config['pygments_style'])

The "File Types" section contains no options by default.


Callbacks
---------

Section objects also support running callbacks when a value is changed. For
example, this annoying plugin warns the user when the encoding is set to
ASCII in the setting dialog::

   from tkinter import messagebox
   from porcupine import settings

   general_config = settings.get_section('General')


   def on_encoding_changed(encoding):
       if encoding.upper() == 'ASCII':
           messagebox.showwarning("ASCII Warning", "ASCII doesn't do æøå!")

   def setup():
       # this runs on_encoding_changed(general_config['encoding'])
       # see the note about run_now below
       general_config.connect('encoding', on_encoding_changed)

There's nothing wrong with using tkinter things like
``messagebox.showwarning()`` in callback functions, but tkinter isn't
thread-safe so you must not set config values from threads.

.. automethod:: section.connect
.. automethod:: section.disconnect


Adding Options
--------------

Unlike with dictionaries, you need to add options to the sections before you
can assign more values to it. This way Porcupine can easily keep track of
default values and let you easily add things to the setting dialog.

.. automethod:: section.add_option
.. automethod:: section.reset


Validating
^^^^^^^^^^

Let's say that you want to store a string in a section. Typically the user
changes string values with e.g. an entry, but you probably don't want to allow
any strings. For example, the only correct values of an ``indent`` option might
be ``'tabs'`` and ``'spaces'``.

.. autoexception:: InvalidValue


Adding Widgets
^^^^^^^^^^^^^^

These methods add a widget to the setting dialog. Unless otherwise mentioned,
the *text* argument is a string displayed on the left side of the widget, and a
|triangle| is displayed on the right side if the user chooses an invalid value.

.. automethod:: section.add_checkbutton
.. automethod:: section.add_entry
.. automethod:: section.add_combobox
.. automethod:: section.add_spinbox


Custom Widgets
^^^^^^^^^^^^^^

If the convenience methods above are not enough for your needs you can also add
any widgets you want to the setting dialog.

You should take care of these things:

   * The section's value is updated immediately when the user does something to
     the widget.
   * The widget itself is updated immediately when the section's value changes
     (e.g. with the reset button).

Many widgets take a ``textvariable`` option that can be set to a
``tkinter.StringVar``, and it does just that -- the widget gets updated when it
changes, and the ``StringVar`` gets updated when the widget changes.

.. automethod:: section.get_var(key, var_type=tkinter.StringVar)
.. automethod:: section.add_frame

.. attribute:: section.content_frame

   This ``ttk.Frame`` represents a tab in the setting dialog. All of the above
   convenience methods and :meth:`add_frame` pack widgets into this.

   You can also add your own widgets to this frame. Usually it's best to pack
   them like ``widget.pack(fill='x')`` for consistency with other widgets.


Rarely Needed Functions
-----------------------

These functions are exposed here for unusual things like
:source:`the poppingtabs plugin <porcupine/plugins/poppingtabs.py>`. You
probably don't need these.

.. autofunction:: show_dialog
.. autofunction:: save
