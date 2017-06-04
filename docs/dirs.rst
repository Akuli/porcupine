:mod:`porcupine.dirs` --- Paths to Porcupine's files
====================================================

.. module:: porcupine.dirs

This small module contains information about where Porcupine is
installed and where its setting files are.

.. data:: cachedir

    User-wide temporary files go here. Currently Porcupine doesn't use
    this for anything, but plugins may use this.

.. data:: configdir

    Porcupine's user-wide settings, color themes and other things are
    here.

.. data:: installdir

    This is the directory where Porcupine is imported from. Example::

        >>> import os
        >>> from porcupine import dirs
        >>> 'dirs.py' in os.listdir(dirs.installdir)
        True
