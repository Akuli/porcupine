import collections
import tkinter
import typing
import warnings

import porcupine
from porcupine import tabs, utils


_actions: 'collections.OrderedDict[str, Action]' = collections.OrderedDict()


class Action:

    def __init__(
            self,
            path: str,
            kind: str,
            callback_or_choices: typing.Union[
                typing.Callable[[], None],
                typing.List[typing.Any],
                None,
            ],
            binding: typing.Optional[str],
            var: typing.Optional[tkinter.Variable]):
        self.path = path
        self.kind = kind
        self.binding = binding
        self._enabled = True

        # this is less crap than subclassing would be
        if kind == 'command':
            assert not isinstance(callback_or_choices, list)
            assert callback_or_choices is not None
            self.callback: typing.Callable[[], None] = callback_or_choices
        elif kind == 'choice':
            assert isinstance(callback_or_choices, list)
            assert var is not None
            self.var = var
            self.choices: typing.List[typing.Any] = callback_or_choices
            self.var.trace_add('write', self._var_set_check)
        elif kind == 'yesno':
            assert var is not None
            self.var = var
        else:
            raise AssertionError("this shouldn't happen")  # pragma: no cover

    def __repr__(self) -> str:
        return '<Action object %r: kind=%r, enabled=%r>' % (
            self.path, self.kind, self.enabled)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, is_enabled: bool) -> None:
        # omitting this check might cause confusing behavior
        if not isinstance(is_enabled, bool):
            raise TypeError("enabled should be True or False, not %r"
                            % (is_enabled,))

        if self._enabled != is_enabled:
            self._enabled = is_enabled
            event = '<<ActionEnabled>>' if is_enabled else '<<ActionDisabled>>'
            porcupine.get_main_window().event_generate(event, data=self.path)

    def _var_set_check(self, *junk: typing.Any) -> None:
        value = self.var.get()
        if value not in self.choices:
            warnings.warn("the var of %r was set to %r which is not one "
                          "of the choices" % (self, value), RuntimeWarning)


def _add_any_action(
        path: str,
        kind: str,
        callback_or_choices: typing.Union[
            typing.Callable[[], None],
            typing.List[typing.Any],
            None,
        ],
        binding: typing.Optional[str],
        var: typing.Optional[tkinter.Variable],
        *,
        filetype_names: typing.Optional[typing.List[str]] = None,
        tabtypes: typing.Optional[typing.Sequence[
            typing.Type[tabs.Tab]]] = None) -> Action:

    if path.startswith('/') or path.endswith('/'):
        raise ValueError("action paths must not start or end with /")
    if filetype_names is not None and tabtypes is not None:
        # python raises TypeError when it comes to invalid arguments
        raise TypeError("only one of filetype_names and tabtypes can be used")
    if path in _actions:
        raise RuntimeError("there's already an action with path %r" % path)

    # event_generate must be before setting action.enabled, this way
    # plugins get a chance to do something to the new action before it's
    # disabled
    action = Action(path, kind, callback_or_choices, binding, var)
    _actions[path] = action
    porcupine.get_main_window().event_generate('<<NewAction>>', data=path)

    if tabtypes is not None or filetype_names is not None:
        if tabtypes is not None:
            actual_tabtypes = tuple(
                # None is the only type(None) object
                type(None) if cls is None else cls
                for cls in tabtypes
            )

            def enable_or_disable(
                    junk_event: typing.Optional[tkinter.Event] = None) -> None:
                tab = porcupine.get_tab_manager().select()
                action.enabled = isinstance(tab, actual_tabtypes)

        if filetype_names is not None:
            def enable_or_disable(
                    junk_event: typing.Optional[tkinter.Event] = None) -> None:
                tab = porcupine.get_tab_manager().select()
                if isinstance(tab, tabs.FileTab):
                    assert filetype_names is not None
                    action.enabled = tab.filetype.name in filetype_names
                else:
                    action.enabled = False

            def on_new_tab(event: utils.EventWithData) -> None:
                tab = event.data_widget()
                if isinstance(tab, tabs.FileTab):
                    tab.bind('<<FiletypeChanged>>', enable_or_disable,
                             add=True)

            utils.bind_with_data(porcupine.get_tab_manager(),
                                 '<<NewTab>>', on_new_tab, add=True)

        enable_or_disable()
        porcupine.get_tab_manager().bind(
            '<<NotebookTabChanged>>', enable_or_disable, add=True)

    # TODO: custom keyboard bindings with a config file or something
    if binding is not None:
        assert kind in {'command', 'yesno'}, repr(kind)

        def bind_callback(event: tkinter.Event) -> utils.BreakOrNone:
            if action.enabled:
                if kind == 'command':
                    action.callback()
                if kind == 'yesno':
                    var = typing.cast(tkinter.BooleanVar, action.var)
                    var.set(not var.get())
                # try to allow binding keys that are used for other
                # things by default
                return 'break'
            return None

        # TODO: warning if it's already bound?
        #
        # bind_all is considered only after the Text-specific binding (try
        # pressing ctrl+o or ctrl+w with some text selected without the
        # following line)
        widget = porcupine.get_main_window()    # any widget would do
        widget.bind_all(binding, bind_callback, add=True)
        widget.bind_class('Text', binding, bind_callback, add=False)

    return action


def add_command(
        path: str,
        callback: typing.Callable[[], None],
        keyboard_binding: typing.Optional[str] = None,
        **kwargs: typing.Any) -> Action:
    """Add a simple action that runs ``callback()``.

    The returned action object has a ``callback`` attribute set to the
    ``callback`` passed to this function.
    """
    return _add_any_action(path, 'command', callback,
                           keyboard_binding, None, **kwargs)


def add_yesno(
        path: str,
        default: typing.Optional[bool] = None,
        keyboard_binding: typing.Optional[str] = None, *,
        var: typing.Optional[tkinter.BooleanVar] = None,
        **kwargs: typing.Any) -> Action:
    """Add an action that appears as a checkbox item in the menubar.

    If *var* is given, it should be a ``tkinter.BooleanVar`` and it's
    used as the ``var`` of the option; otherwise a new ``BooleanVar`` is
    created. *default* should be True or False, but it may be omitted if
    *var* is specified.
    """
    if var is None:
        if default is None:
            raise TypeError("specify default or var")
        var = tkinter.BooleanVar()
        var.set(default)
    elif default is not None:
        var.set(default)

    return _add_any_action(path, 'yesno', None,
                           keyboard_binding, var, **kwargs)


def add_choice(
        path: str,
        choices: typing.List[typing.Any],
        default: typing.Optional[typing.Any] = None,
        *,
        var: typing.Optional[tkinter.Variable] = None,
        **kwargs: typing.Any) -> Action:
    """Add an action for choosing one from a list of choices.

    :source:`The menubar plugin <porcupine/plugins/menubar.py>` displays
    these actions as submenus that contain radio button items.

    If given, *default* should be an element of *choices*. It defaults
    to ``var.get()`` if ``var`` is given, and ``choices[0]`` if it's not
    given.

    If *var* is given, it should be a ``tkinter.StringVar`` and it's
    used as the ``var`` of the option; otherwise a new ``StringVar`` is
    created.
    """
    if var is None:
        if default is None:
            default = choices[0]
        elif default not in choices:
            raise ValueError("default value %r is not in choices" % (default,))
        var = tkinter.StringVar()
        var.set(default)
    else:
        if var.get() not in choices:
            raise ValueError("the var's current value %r is not in choices"
                             % var.get())
        if default is not None:
            if default not in choices:
                raise ValueError("default value %r is not in choices"
                                 % (default,))
            var.set(default)

    return _add_any_action(path, 'choice', choices, None, var, **kwargs)


def get_action(action_path: str) -> Action:
    """Look up and return an existing action object by its path."""
    return _actions[action_path.rstrip('/')]


def get_all_actions() -> typing.List[Action]:
    """Return a list of all existing action objects in arbitrary order.

    Note that plugins like :source:`the menubar <porcupine/plugins/menubar.py>`
    should also use the ``<<NewAction>>`` virtual event documented
    `above <#action-adding-functions>`_.
    """
    return list(_actions.values())
