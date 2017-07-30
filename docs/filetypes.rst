File Types
==========

Porcupine supports editing several different kinds of files. This page is all
about customizing its behaviour for each file type.


filetypes.ini
-------------

This file contains a bunch of filetype-specific settings. Porcupine's
default settings should be good enough for most things, but this file
lets you customize everything.

Porcupine creates a ``filetypes.ini`` when it's started for the first
time. By default, it contains comments that explain how it works and the
default settings that Porcupine is using. The easiest way to edit this
file is to open *Porcupine Settings* from the *Edit* menu and click the
*Edit filetypes.ini* button.

If the file contains invalid values, Porcupine will ignore the whole
file on startup but it will log a warning. The easiest way to see it is
to run Porcupine from a command prompt or terminal. Here's a command for
Windows command prompt:

.. code-block:: none

   py -m porcupine

And here's the equivalent terminal command for Mac OSX and Linux:

.. code-block:: none

   python3 -m porcupine


The ``porcupine.filetypes`` module
----------------------------------

.. module:: porcupine.filetypes

Everything related to `filetypes.ini`_ is implemented here.

.. data:: filetypes

   This is a ``{name: filetype_object}`` dictionary where the names
   correspond to sections of `filetypes.ini`_. When Porcupine starts, it
   initializes this dictionary based on `filetypes.ini`_.

.. autoclass:: FileType
   :members:
