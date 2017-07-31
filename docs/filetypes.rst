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
default settings that Porcupine is using.

The easiest way to edit this file is to open *Porcupine Settings* from
the *Edit* menu and click the *Edit filetypes.ini* button. Porcupine
will also syntax highlight the file specially so that anything incorrect
won't be colored, and it's hard to get things wrong. If the file still
contains invalid values, Porcupine will ignore it on startup.


The ``porcupine.filetypes`` module
----------------------------------

.. module:: porcupine.filetypes

Everything related to the ``filetypes.ini`` file is here.

.. data:: filetypes

   This is a ``{name: filetype_object}`` dictionary where the names
   correspond to sections of `filetypes.ini`_. When Porcupine starts, it
   initializes this dictionary based on ``filetypes.ini``.

.. autoclass:: FileType
   :members:
