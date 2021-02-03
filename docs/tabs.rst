:mod:`porcupine.tabs` --- The tab manager and tabs in it
========================================================

.. module:: porcupine.tabs

As usual, I recommend reading
:ref:`the plugin writing introduction <plugin-intro>` if you haven't read it
yet. See :source:`porcupine/tabs.py` if you're interested in how the tabs work
and you'd like to use their code in your own projects.

.. autoclass:: TabManager
   :members:

.. autoclass:: Tab
   :members:

.. specifying members explicitly to avoid showing some overrided things

.. autoclass:: FileTab
   :members: open_file, is_modified, save, save_as, reload, reload_is_needed
