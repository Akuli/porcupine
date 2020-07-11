import atexit
import codecs
import collections.abc
import functools
import json
import logging
import os
import sys
import tkinter
import tkinter.font as tkfont   # type: ignore
from tkinter import messagebox, ttk
import types
import typing

# the pygments stuff is just for _validate_pygments_style_name()
import pygments.styles      # type: ignore
import pygments.util        # type: ignore

# get_main_window and get_tab_manager must not be imported from
# porcupine because it imports this before exposing the getter
# functions, and the getter functions cannot be imported from
# porcupine._run because that imports this file (lol)
# that's why "import porcupine"
import porcupine
from porcupine import dirs, images, utils
from porcupine.filetypes import get_all_filetypes


log = logging.getLogger(__name__)


# this is a custom exception because plain ValueError is often raised
# when something goes wrong unexpectedly
class InvalidValue(Exception):
    """Raise this in a callback if the value is invalid.

    Example::

        wat_config = settings.get_section('Wat Wat')

        def validate_indent(indent):
            if indent not in ('tabs', 'spaces'):
                raise settings.InvalidValue(
                    "invalid indent %r, should be 'tabs' or 'spaces'"
                    % repr(indent))

        wat_config.add_option('indent', default='spaces')
        wat_config.connect('indent', validate_indent)

    .. note::
        Be sure to connect validator callbacks before anything else is
        connected. The callbacks are ran in the same order as they are
        connected, and running other callbacks with an invalid value is
        probably not what you want.

    There's no need to do checks like ``isinstance(indent, str)``.
    Python is a dynamically typed language.

    You can also catch ``InvalidValue`` to check if setting a value
    succeeded::

        try:
            wat_config['indent'] = 'wat wat'
        except InvalidValue:
            print("'wat wat' is not a valid indent :(")
    """


# globals ftw
_sections: typing.Dict[str, '_ConfigSection'] = {}
_loaded_json: typing.Dict[str, typing.Dict[str, typing.Union[str, int]]] = {}

# the "Porcupine Settings" window
_dialog: typing.Optional[tkinter.Toplevel] = None

# main widget in the dialog
_notebook: typing.Optional[ttk.Notebook] = None


def get_section(section_name: str) -> _ConfigSection:
    """Return a section object, creating it if it doesn't exist yet.

    The *section_name* is a title of a tab in the *Porcupine Settings*
    dialog, such as ``'General'`` or ``'File Types'``.
    """
    _init()
    try:
        return _sections[section_name]
    except KeyError:
        _sections[section_name] = _ConfigSection(section_name)
        return _sections[section_name]


_CallbackType = typing.Callable[[typing.Any], None]

# T represents a subclass of tkinter.Variable. Don't know if there's a better
# way to tell that to mypy than passing tkinter.Variable twice...
T = typing.TypeVar('T', tkinter.Variable, tkinter.Variable)


class _OptionInfo(types.SimpleNamespace):
    default: typing.Any     # not validated
    reset: bool
    callbacks: typing.List[typing.Callable[[typing.Any], None]]
    errorvar: tkinter.BooleanVar


class _ConfigSection(typing.MutableMapping[str, typing.Any]):

    def __init__(self, name: str) -> None:
        if _notebook is None:
            raise RuntimeError("%s.init() wasn't called" % __name__)

        self.content_frame = ttk.Frame(_notebook)
        _notebook.add(self.content_frame, text=name)

        self._name = name
        self._infos: typing.Dict[str, _OptionInfo] = {}
        self._var_cache: typing.Dict[str, tkinter.Variable] = {}

    def add_option(self, key: str, default: typing.Any, *,
                   reset: bool = True) -> None:
        """Add a new option without adding widgets to the setting dialog.

        ``section[key]`` will be *default* unless something else is
        specified.

        If *reset* is True, the setting dialog's reset button sets this
        option to *default*.

        .. note::
            The *reset* argument should be False for settings that
            cannot be changed with the dialog. That way, clicking the
            reset button resets only the settings that are shown in the
            dialog.
        """
        self._infos[key] = _OptionInfo(
            default=default,        # not validated
            reset=reset,
            callbacks=[],
            errorvar=tkinter.BooleanVar(),  # true when the triangle is showing
        )

    def __setitem__(self, key: str, value: typing.Any) -> None:
        info = self._infos[key]

        old_value = self[key]
        try:
            _loaded_json[self._name][key] = value
        except KeyError:
            _loaded_json[self._name] = {key: value}

        if value != old_value:
            log.debug("%s: %r was set to %r, running %d callbacks",
                      self._name, key, value, len(info.callbacks))
            for func in info.callbacks:
                try:
                    func(value)
                except InvalidValue as e:
                    _loaded_json[self._name][key] = old_value
                    raise e
                except Exception:
                    try:
                        func_name = func.__module__ + '.' + func.__qualname__
                    except AttributeError:
                        func_name = repr(func)
                    log.exception("%s: %s(%r) didn't work", self._name,
                                  func_name, value)

    def __getitem__(self, key: str) -> typing.Any:
        try:
            return _loaded_json[self._name][key]
        except KeyError:
            return self._infos[key].default

    # the abc requires this
    def __delitem__(self, key: str) -> typing.NoReturn:
        raise TypeError("cannot delete options")

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._infos.keys())

    def __len__(self) -> int:
        return len(self._infos)

    def reset(self, key: str) -> None:
        """Set ``section[key]`` back to the default value.

        The value is always reset to the *default* argument passed to
        :meth:`add_option`, regardless of its *reset* argument.

        Resetting is useful for e.g. key bindings. For example, pressing
        Ctrl+0 resets ``font_size``.
        """
        self[key] = self._infos[key].default

    def connect(self, key: str, callback: _CallbackType,
                run_now: bool = True) -> None:
        """
        Schedule ``callback(section[key])`` to be called when the value
        of an option changes.

        If *run_now* is True, ``callback(section[key])`` is also called
        immediately when ``connect()`` is called, and the option is
        reset if the callback raises :exc:`InvalidValue`.

        .. note::
            *run_now* is True by default, so if you don't want to run
            the callback right away you need an explicit
            ``run_now=False``.

        More than one callback can be connected to the same key.
        """
        if run_now:
            try:
                callback(self[key])
            except InvalidValue:
                try:
                    func_name = (callback.__module__ + '.' +
                                 callback.__qualname__)
                except AttributeError:
                    func_name = repr(callback)
                log.warning(
                    "%s: %r value %r is invalid according to %s, resetting"
                    % (self._name, key, self[key], func_name))
                self.reset(key)
        self._infos[key].callbacks.append(callback)

    def disconnect(self, key: str, callback: _CallbackType) -> None:
        """Undo a :meth:`~connect` call."""
        self._infos[key].callbacks.remove(callback)

    # returns an image the same size as the triangle image, but empty
    @staticmethod
    def _get_fake_triangle(
            cache: typing.List[tkinter.PhotoImage] = []) -> tkinter.PhotoImage:
        if not cache:
            cache.append(tkinter.PhotoImage(
                width=images.get('triangle').width(),
                height=images.get('triangle').height()))
            atexit.register(cache.clear)     # see images/__init__.py
        return cache[0]

    def get_var(
        self, key: str,
        var_type: typing.Type[T] = tkinter.StringVar,
    ) -> T:
        """Return a tkinter variable that is bound to an option.

        Changing the value of the variable updates the config section,
        and changing the value in the section also sets the variable's
        value.

        This returns a ``StringVar`` by default, but you can use the
        ``var_type`` argument to change that. For example,
        ``var_type=tkinter.BooleanVar`` is suitable for an option that
        is meant to be True or False.

        If an invalid value is set to the variable, it is not set to the
        section but the triangles in the frames returned by
        :meth:`add_frame` are shown.

        Calling this function multiple times with different ``var_type``
        arguments raises :exc:`TypeError`.
        """
        if key in self._var_cache:
            if not isinstance(self._var_cache[key], var_type):
                raise TypeError("get_var(%r, var_type) was called multiple "
                                "times with different var types" % key)
            return self._var_cache[key]

        info = self._infos[key]
        var = var_type()

        def var2config(*junk: typing.Any) -> None:
            try:
                value = var.get()
            except (tkinter.TclError, ValueError):
                # example: var_type is IntVar and the actual value is 'lol'
                # not-very-latest pythons use int() and raise ValueError
                info.errorvar.set(True)
                return

            try:
                self[key] = value
            except InvalidValue:
                info.errorvar.set(True)
                return

            info.errorvar.set(False)

        self.connect(key, var.set)      # runs var.set
        var.trace_add('write', var2config)

        self._var_cache[key] = var
        return var

    def add_frame(
            self, triangle_key: typing.Optional[str] = None) -> ttk.Frame:
        """Add a ``ttk.Frame`` to the dialog and return it.

        The frame will contain a label that displays a |triangle| when
        the value of the variable from :meth:`get_var` is invalid. The
        triangle label is packed with ``side='right'``.

        For example, :meth:`add_checkbutton` works roughly like this::

            frame = section.add_frame(key)
            var = section.get_var(key, tkinter.BooleanVar)
            ttk.Checkbutton(frame, text=text, variable=var).pack(side='left')

        """
        frame = ttk.Frame(self.content_frame)
        frame.pack(fill='x')

        if triangle_key is not None:
            errorvar = self._infos[triangle_key].errorvar
            triangle_label = ttk.Label(frame)
            triangle_label.pack(side='right')

            def on_errorvar_changed(*junk: typing.Any) -> None:
                if errorvar.get():
                    triangle_label['image'] = images.get('triangle')
                else:
                    triangle_label['image'] = self._get_fake_triangle()

            errorvar.trace_add('write', on_errorvar_changed)
            on_errorvar_changed()

        return frame

    # TODO: document this
    def add_label(self, text: str) -> ttk.Label:
        frame = self.add_frame()
        label = ttk.Label(frame, text=text)
        label.pack(fill='x', pady=10)

        def wrap_on_resize(event: tkinter.Event) -> None:
            assert event.width != '??'
            label['wraplength'] = event.width

        frame.bind('<Configure>', wrap_on_resize, add=True)
        return label

    def add_checkbutton(self, key: str, text: str) -> None:
        """Add a ``ttk.Checkbutton`` that sets an option to a bool."""
        var = self.get_var(key, tkinter.BooleanVar)
        assert isinstance(var, tkinter.BooleanVar)   # TODO: why this needed?
        ttk.Checkbutton(self.add_frame(key), text=text,
                        variable=var).pack(side='left')

    def add_entry(self, key: str, text: str) -> None:
        """Add a ``ttk.Entry`` that sets an option to a string."""
        frame = self.add_frame(key)
        ttk.Label(frame, text=text).pack(side='left')

        var = self.get_var(key)
        assert isinstance(var, tkinter.StringVar)   # TODO: why this needed?
        ttk.Entry(frame, textvariable=var).pack(side='right')

    def add_combobox(self, key: str, choices: typing.List[str], text: str, *,
                     case_sensitive: bool = True) -> None:
        """Add a ``ttk.Combobox`` that sets an option to a string.

        The combobox will contain each string in *choices*.

        A `validator callback <Validating>`_ that ensures the value is
        in *choices* is also added. If *case_sensitive* is False,
        :meth:`str.casefold` is used when comparing the strings.
        """
        def validator(value: str) -> None:
            if case_sensitive:
                ok = (value in choices)
            else:
                ok = (value.casefold() in map(str.casefold, choices))
            if not ok:
                raise InvalidValue("%r is not a valid %r value"
                                   % (value, key))

        self.connect(key, validator)

        frame = self.add_frame(key)
        ttk.Label(frame, text=text).pack(side='left')

        var = self.get_var(key)
        assert isinstance(var, tkinter.StringVar)   # TODO: why this needed?
        ttk.Combobox(frame, values=choices,
                     textvariable=var).pack(side='right')

    def add_spinbox(
            self, key: str, minimum: int, maximum: int, text: str) -> None:
        """
        Add a :class:`utils.Spinbox <porcupine.utils.Spinbox>` that sets
        an option to an integer.

        The *minimum* and *maximum* arguments are used as the bounds for
        the spinbox. A `validator callback <Validating>`_ that makes
        sure the value is between them is also added.

        Note that *minimum* and *maximum* are inclusive, so
        ``minimum=3, maximum=5`` means that 3, 4 and 5 are valid values.
        """
        def validator(value: int) -> None:
            if value < minimum:
                raise InvalidValue(f"{value} is too small")
            if value > maximum:
                raise InvalidValue(f"{value} is too big")

        self.connect(key, validator)

        frame = self.add_frame(key)
        ttk.Label(frame, text=text).pack(side='left')

        var = self.get_var(key, tkinter.IntVar)
        assert isinstance(var, tkinter.IntVar)      # TODO: why is this needed?
        utils.Spinbox(frame, textvariable=var,
                      from_=minimum, to=maximum).pack(side='right')


def _needs_reset() -> bool:
    for section in _sections.values():
        for key, info in section._infos.items():
            if info.default != section[key]:
                return True
    return False


def _do_reset() -> None:
    if not _needs_reset:
        messagebox.showinfo("Reset Settings",
                            "You are already using the default settings.")
        return

    if not messagebox.askyesno(
            "Reset Settings", "Are you sure you want to reset all settings?",
            parent=_dialog):
        return

    for section in _sections.values():
        for key, info in section._infos.items():
            if info.reset:
                section[key] = info.default
    messagebox.showinfo(
        "Reset Settings", "All settings were reset to defaults.",
        parent=_dialog)


def _validate_encoding(name: str) -> None:
    try:
        codecs.lookup(name)
    except LookupError as e:
        raise InvalidValue from e


def _validate_pygments_style_name(name: str) -> None:
    try:
        pygments.styles.get_style_by_name(name)
    except pygments.util.ClassNotFound as e:
        raise InvalidValue(str(e)) from None


def _init() -> None:
    global _dialog
    global _notebook

    if _dialog is not None:
        # already initialized
        return

    # tkinter weirdness: withdraw returns '' but protocol callback needs to
    # return None. Actually it works if it returns '', and the return value
    # gets ignored, but this is the price one has to pay for accurate type
    # hints.
    def withdraw_the_dialog() -> None:
        assert _dialog is not None
        _dialog.withdraw()

    _dialog = tkinter.Toplevel()
    _dialog.withdraw()        # hide it for now
    _dialog.title("Porcupine Settings")
    _dialog.protocol('WM_DELETE_WINDOW', withdraw_the_dialog)
    _dialog.geometry('500x350')

    big_frame = ttk.Frame(_dialog)
    big_frame.pack(fill='both', expand=True)
    _notebook = ttk.Notebook(big_frame)
    _notebook.pack(fill='both', expand=True)
    ttk.Separator(big_frame).pack(fill='x')
    buttonframe = ttk.Frame(big_frame)
    buttonframe.pack(fill='x')
    for text, command in [("Reset", _do_reset), ("OK", withdraw_the_dialog)]:
        ttk.Button(buttonframe, text=text, command=command).pack(side='right')

    assert not _loaded_json
    try:
        with open(os.path.join(dirs.configdir, 'settings.json'), 'r') as file:
            _loaded_json.update(json.load(file))
    except FileNotFoundError:
        pass      # use defaults everywhere

    general = get_section('General')   # type: _ConfigSection

    fixedfont = tkfont.Font(name='TkFixedFont', exists=True)
    font_families = sorted(family for family in tkfont.families()
                           # i get weird fonts starting with @ on windows
                           if not family.startswith('@'))

    general.add_option('font_family', fixedfont.actual('family'))
    general.add_combobox('font_family', font_families, "Font Family:",
                         case_sensitive=False)

    # negative font sizes have a special meaning in tk and the size is negative
    # by default, that's why the stupid hard-coded default size 10
    general.add_option('font_size', 10)
    general.add_spinbox('font_size', 3, 1000, "Font Size:")

    # when font_family changes:  fixedfont['family'] = new_family
    # when font_size changes:    fixedfont['size'] = new_size
    general.connect(
        'font_family', functools.partial(fixedfont.__setitem__, 'family'))
    general.connect(
        'font_size', functools.partial(fixedfont.__setitem__, 'size'))

    # TODO: file-specific encodings
    general.add_option('encoding', 'UTF-8')
    general.add_entry('encoding', "Encoding of opened and saved files:")
    general.connect('encoding', _validate_encoding)

    general.add_option('pygments_style', 'default', reset=False)
    general.connect('pygments_style', _validate_pygments_style_name)

    def edit_it() -> None:
        # porcupine/tabs.py imports this file
        # these local imports feel so evil xD  MUHAHAHAA!!!
        from porcupine import tabs

        path = dirs.configdir / 'filetypes.ini'
        manager = porcupine.get_tab_manager()
        manager.add_tab(tabs.FileTab.open_file(manager, path))
        assert _dialog is not None
        _dialog.withdraw()

    filetypes = get_section('File Types')
    filetypes.add_label(
        "Currently there's no GUI for changing filetype specific settings, "
        "but they're stored in filetypes.ini and you can edit it yourself.")
    ttk.Button(filetypes.add_frame(), text="Edit filetypes.ini",
               command=edit_it).pack(anchor='center')

    names = [filetype.name for filetype in get_all_filetypes()]
    filetypes.add_label(
        "You can use the following option to choose which filetype "
        "Porcupine should use when you create a new file in Porcupine. You "
        "can change the filetype after creating the file by clicking "
        "Filetypes in the menu bar.")
    filetypes.add_option('default_filetype', 'Plain Text')
    filetypes.add_combobox('default_filetype', names,
                           "Default filetype for new files:")


def show_dialog() -> None:
    """Show the "Porcupine Settings" dialog.

    This function is called when the user opens the dialog from the menu.
    """
    _init()
    assert _notebook is not None
    assert _dialog is not None

    # hide sections with no widgets in the content_frame
    # add and hide preserve order and title texts
    for name, section in _sections.items():
        if section.content_frame.winfo_children():
            _notebook.add(section.content_frame)
        else:
            _notebook.hide(section.content_frame)

    _dialog.transient(porcupine.get_main_window())
    _dialog.deiconify()


def save() -> None:
    """Save the settings to the config file.

    Note that :func:`porcupine.run` always calls this before it returns,
    so usually you don't need to worry about this yourself.
    """
    if _loaded_json:
        # there's something to save
        # if two porcupines are running and the user changes settings
        # differently in them, the settings of the one that's closed
        # first are discarded
        with open(os.path.join(dirs.configdir, 'settings.json'), 'w') as file:
            json.dump(_loaded_json, file)


# docs/settings.rst relies on this
# FIXME: the [source] links of section methods don't work :(
if 'sphinx' in sys.modules:
    section = _ConfigSection
