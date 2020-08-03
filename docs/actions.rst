:mod:`porcupine.actions` --- Add stuff to the menubar
=====================================================

.. module:: porcupine.actions

An **action** is displayed to the user as an item in the menubar, and actions
are often associated with a global keyboard binding; that is, a keyboard
binding not limited to a specific widget. For example, Ctrl+C for copying is
not global because it behaves differently depending on which widget is
selected, but Porcupine's Ctrl+N binding is global because Ctrl+N always
creates a new file. In fact, Ctrl+N and the "New File" button in the "File"
menu are both created with just one :func:`add_command` call.

See :ref:`the plugin writing introduction <plugin-intro>` for a complete
example plugin that uses this module.


Action Objects
--------------

Use one of the action adding functions documented below instead of trying to
create a new action yourself with ``Action(some arguments here)``.

.. TODO: move this documentation to actions.py?

.. class:: Action

    .. attribute:: path
        :type: str

        A string consisting of user-readable parts joined with ``/``, e.g.
        ``'File/New File'``.

    .. attribute:: kind
        :type: Literal['command', 'yesno', 'choice']

        This string indicates which `adding function <#action-adding-functions>`_ the action came from.

    .. attribute:: binding
        :type: str

        A string suitable for tkinter's ``bind()`` method, e.g. ``'<Control-n>'``.
        :source:`The menubar plugin <porcupine/plugins/menubar.py>` uses
        :func:`porcupine.utils.get_keyboard_shortcut` when it displays things like
        ``Ctrl+N`` next to *New File*. Can be None for no binding.

    .. attribute:: enabled
        :type: bool

        True if the action is currently usable, and False otherwise. The menubar
        makes disabled actions gray.

    .. virtualevent:: ActionEnabled
    .. virtualevent:: ActionDisabled

        These virtual events are generated on the **main window** when the
        :attr:`.enabled` attribute of any :class:`Action` is changed.

        Setting :attr:`.enabled` to its current value does not generate
        these events. They are only created when :attr:`.enabled` is actually
        changed.

        The ``data_string`` of the event is set to the action name.
        For example::

            from porcupine import actions, get_main_window, utils

            def on_action_enabled(event):
                action = actions.get_action(event.data_string)
                ...

            utils.bind_with_data(get_main_window(), '<<ActionEnabled>>',
                                 on_action_enabled, add=True)

        .. seealso::
            :func:`porcupine.get_main_window`,
            :func:`porcupine.utils.bind_with_data`

    .. attribute:: callback
        :type: Callable[[], None]

        .. note:: Only actions added with :func:`add_command` have this attribute.

        This is the callback function passed to :func:`add_command`. Only
        ``'command'`` actions have this attribute.

        Example::

            if action.enabled:
                action.callback()

    .. attribute:: var
        :type: tkinter.Variable

        .. note:: Only actions added with :func:`add_yesno` and :func:`add_choice` have this attribute.

        Only ``'yesno'`` and ``'choice'`` actions have a ``var`` attribute, and
        it's set to a tkinter variable object representing the current state. For
        ``'yesno'`` actions, this is a ``tkinter.BooleanVar`` that is set to
        ``True`` when the menuitem is checked and ``False`` when it's not. The
        ``var`` of ``'choice'`` actions is a ``tkinter.StringVar`` set to the
        currently selected choice.

    .. attribute:: choice_action.choices

        Only ``'choice'`` actions have this attribute, and it's set to the
        *choices* passed to :func:`add_choice`.


Action Adding Functions
-----------------------

.. TODO: .. virtualevent:: NewAction

These functions return the action object they add. Adding a new action also
generates a ``<<NewAction>>`` virtual event on the main window with the data
set to the action name, similarly to how the :attr:`~any_action.enabled`
attribute works. Actions are usually added in the ``setup()`` function of a
plugin, but adding more actions later works as well.

.. autofunction:: add_command
.. autofunction:: add_yesno
.. autofunction:: add_choice

The above functions take these optional keyword-only arguments as ``**kwargs``:

.. TODO: the way these are documented sucks

*filetype_names: List[str]*
    Enable and disable the action automatically so that it's enabled only when
    a file of a specific type is being edited. For example,
    ``filetype_names=['Python']`` is useful for a Python-specific action.

    This should be a list or set of
    :attr:`~porcupine.filetypes.somefiletype.name` attributes of
    :ref:`filetype objects <filetype-objects>`. The action is disabled if the
    current tab is not a :class:`~porcupine.tabs.FileTab`.

*tabtypes: List[Type[porcupine.tabs.Tab]]*
    Enable and disable the action automatically so that it's enabled only when
    the current tab is of a specific type.

    If given, this should be a listor set of :class:`~porcupine.tabs.Tab`
    subclasses, or ``None`` to also enable the action when there are no tabs.

Using *filetype_names* and *tabtypes* in the same function call doesn't work.


Other Functions
---------------

.. autofunction:: get_action
.. autofunction:: get_all_actions
