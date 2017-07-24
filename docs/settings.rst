:mod:`porcupine.settings` --- Porcupine's setting manager
=========================================================

.. module:: porcupine.settings

This module contains Porcupine's settings and color themes.


The config
----------

The ``config`` variable is set to an object that behaves like a
``{(section, configkey): value}`` dictionary where *section* and
*configkey* are strings. The config object also support things like
default values and running callbacks when something changes. Note that
``config['section', 'key']`` does the same thing as
``config[('section', 'key')]``, so usually you don't need to use
parentheses when setting or getting values.

Adding Keys
^^^^^^^^^^^

Unlike with regular dictionaries, you need to add keys to the config
before you can set them to a value.

..  documenting methods from an instance like this seems to work,
    i'll fix this if this breaks in a newer sphinx

.. automethod:: porcupine.settings.config.add_key
.. automethod:: porcupine.settings.config.add_bool_key
.. automethod:: porcupine.settings.config.add_int_key

Callback Hooks
^^^^^^^^^^^^^^

.. attribute:: hooks

    A ``{(section, key): hook}`` dictionary where the hooks are
    :class:`utils.CallbackHook <porcupine.utils.CallbackHook>` objects.
    When a value is set, the matching callback hook is ran with the new
    value as the only argument.

.. automethod:: porcupine.settings.config.connect
.. automethod:: porcupine.settings.config.disconnect

.. attribute:: anything_changed_hook

    Callbacks connected to this
    :class:`CallbackHook <porcupine.utils.CallbackHook>` are ran like
    ``callback(section, key, value)`` when anything is set to the
    config.

Other things
^^^^^^^^^^^^

.. automethod:: porcupine.settings.config.reset
.. autoexception:: porcupine.settings.InvalidValue
