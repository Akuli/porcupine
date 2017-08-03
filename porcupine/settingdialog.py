"""A dialog for changing the settings."""
# This uses ttk widgets instead of tk widgets because it needs
# ttk.Combobox anyway and mixing the widgets looks inconsistent.

import os
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

import porcupine
from porcupine import utils
from porcupine.settings import config, dirs, InvalidValue

try:
    # There's no ttk.Spinbox for some reason. Maybe this will be fixed
    # later?
    _TtkSpinbox = ttk.Spinbox
except AttributeError:
    # At least not yet, but implementing this is easy to do by reading
    # the code of ttk.Combobox.
    class _TtkSpinbox(ttk.Entry):
        def __init__(self, master=None, *, from_=None, **kwargs):
            if from_ is not None:
                kwargs['from'] = from_  # this actually works
            super().__init__(master, 'ttk::spinbox', **kwargs)


PADDING = {'padx': 5, 'pady': 2}


class Triangle(ttk.Label):
    """Really simple widget. Just to avoid repetitive and repetitive code."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        img = utils.get_image('triangle.gif')

        # i'm not sure why this _fake_img reference doesn't cause
        # similar problems as functools.lru_cache() in utils.get_image()
        # (see the comments there for weird stuff)
        self._fake_img = tk.PhotoImage(width=img.width(), height=img.height())
        self['image'] = self._fake_img

    def show(self):
        self['image'] = utils.get_image('triangle.gif')

    def hide(self):
        self['image'] = self._fake_img


class Checkbutton(ttk.Checkbutton):
    """A checkbutton that sets ``config[configkey]`` to True or False."""

    def __init__(self, parent, configkey, **kwargs):
        super().__init__(parent, **kwargs)
        self._key = configkey
        self._var = self['variable'] = tk.BooleanVar()
        self._var.trace('w', self._to_config)
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        config[self._key] = self._var.get()


class Entry(ttk.Frame):
    """A frame with an entry and a triangle label.

    The entry is available as an ``entry`` attribute. Its text is the
    same as ``config[configkey]``.
    """

    def __init__(self, parent, configkey, **kwargs):
        super().__init__(parent)
        self.entry = ttk.Entry(self, **kwargs)
        self.entry.pack(side='left', fill='both', expand=True)
        self._triangle = Triangle(self)
        self._triangle.pack(side='right')

        self._key = configkey
        self._var = self.entry['textvariable'] = tk.StringVar()
        self._var.trace('w', self._to_config)
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        try:
            config[self._key] = self._var.get()
            self._triangle.hide()
        except InvalidValue:
            self._triangle.show()


class Spinbox(ttk.Frame):
    """A spinbox widget that sets ``config[configkey]`` to an integer."""

    def __init__(self, parent, configkey, **kwargs):
        super().__init__(parent)
        self.spinbox = _TtkSpinbox(self, **kwargs)
        self.spinbox.pack(side='left', fill='both', expand=True)
        self._triangle = Triangle(self)
        self._triangle.pack(side='right')

        self._key = configkey
        self._var = self['textvariable'] = tk.StringVar()
        self._var.trace('w', self._to_config)

        # self._var.set() will be called with an integer, but tkinter
        # str()s it because everything is a string in Tcl
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        try:
            config[self._key] = int(self._var.get())
            self._triangle.hide()
        except (ValueError, InvalidValue):
            self._triangle.show()


class FontSelector(ttk.Frame):
    """A combination of a combobox and spinbox for choosing fonts.

    The combobox and spinbox will change ``config[section, 'family']``
    and ``config[section, 'size']``.
    """

    def __init__(self, parentwidget, **kwargs):
        super().__init__(parentwidget, **kwargs)

        self._familyvar = tk.StringVar()
        self._sizevar = tk.StringVar()
        familycombo = ttk.Combobox(self, textvariable=self._familyvar,
                                   width=15, values=self._get_families())
        familycombo.pack(side='left')
        size_spinbox = _TtkSpinbox(
            self, from_=3, to=1000, width=4, textvariable=self._sizevar)
        size_spinbox.pack(side='left')
        self._triangle = Triangle(self)
        self._triangle.pack(side='right')

        self._fixedfont = tkfont.Font(name='TkFixedFont', exists=True)
        config.connect('Font', 'family', self._family_from_config,
                       run_now=True)

        # tkinter converts everything to strings, so setting an integer
        # to a StringVar works ok
        # FIXME: can the size be negative?
        config.connect('Font', 'size', self._sizevar.set, run_now=True)

        self._familyvar.trace('w', self._to_config)
        self._sizevar.trace('w', self._to_config)

        # _family2config and _size2config can't just call show_triangle()
        # because it must be hidden if e.g. size is ok but family is not
        self._family_ok = self._size_ok = True

    @staticmethod
    def _get_families():
        # get weird of weird fonts starting with @ on windows, delete
        # duplicates with a set and sort case-insensitively
        return sorted({family for family in tkfont.families()
                       if family[0] != '@'}, key=str.casefold)

    def _family_from_config(self, junk):
        # config['Font', 'family'] can be None, but porcupine.settings
        # should set all font changes to TkFixedFont
        self._familyvar.set(self._fixedfont.actual('family'))

    # this is combined into one function because otherwise figuring out
    # when to show the triangle would be harder
    def _to_config(self, *junk):
        try:
            # if family is ok and size is not the family gets set but
            # the size doesn't, but it doesn't matter
            config['Font', 'family'] = self._familyvar.get()
            config['Font', 'size'] = int(self._sizevar.get())
            self._triangle.hide()
        except (ValueError, InvalidValue) as e:
            self._triangle.show()


_dialog = None


def get_main_area():
    assert _dialog is not None, "init() wasn't called"
    return _dialog._main_area


def show():
    assert _dialog is not None, "init() wasn't called"
    _dialog.deiconify()


def _reset():
    confirmed = messagebox.askyesno(
        "Reset", "Do you want to reset all settings to defaults?",
        parent=_dialog)
    if confirmed:
        config.reset()
        messagebox.showinfo(
            "Reset", "All settings were set to defaults.", parent=_dialog)


def init():
    global _dialog
    assert _dialog is None, "init() was called twice"

    _dialog = tk.Toplevel(porcupine.get_main_window())
    _dialog.transient(porcupine.get_main_window())
    _dialog.withdraw()
    _dialog.title("Porcupine Settings")
    _dialog.geometry('500x300')
    _dialog.protocol('WM_DELETE_WINDOW', _dialog.withdraw)

    # create a ttk frame that fills the whole toplevel because tk
    # widgets have a different color than ttk widgets on my system and
    # there's no ttk.Toplevel
    big_frame = ttk.Frame(_dialog)
    big_frame.pack(fill='both', expand=True)

    main_area = ttk.Frame(big_frame)
    main_area.pack(fill='both', expand=True, **PADDING)
    _dialog._main_area = main_area      # see get_main_area()

    ttk.Separator(big_frame).pack(fill='x', **PADDING)

    button_frame = ttk.Frame(big_frame)
    button_frame.pack(anchor='e', **PADDING)
    ttk.Button(button_frame, text="OK", command=_dialog.withdraw).pack(
        side='right', **PADDING)
    ttk.Button(button_frame, text="Reset everything", command=_reset).pack(
        side='right', **PADDING)

    general = ttk.LabelFrame(main_area, text="General")
    general.pack(fill='x', **PADDING)
    general.grid_columnconfigure(0, weight=1)

    ttk.Label(general, text="Encoding of opened and saved files:").grid(
        row=0, column=0, sticky='w', **PADDING)
    Entry(general, ('Files', 'encoding')).grid(
        row=0, column=1, sticky='e', **PADDING)
    Checkbutton(
        general, ('Files', 'add_trailing_newline'),
        text="Make sure that files end with an empty line when saving"
    ).grid(row=1, columnspan=2, sticky='we', **PADDING)
    ttk.Label(general, text="The font:").grid(
        row=2, column=0, sticky='w', **PADDING)
    FontSelector(general).grid(row=2, column=1, sticky='e', **PADDING)
    ttk.Separator(general).grid(row=3, columnspan=2, **PADDING)

    langspec = ttk.LabelFrame(main_area, text="Filetype specific settings")
    langspec.pack(fill='x', **PADDING)

    label = ttk.Label(langspec, text=(
        "Currently there's no GUI for changing filetype specific "
        "settings, but they're stored in filetypes.ini and you can "
        "edit it yourself too."))
    langspec.bind(      # automatic wrapping
        '<Configure>',
        lambda event: label.config(wraplength=event.width),
        add=True)
    label.pack(**PADDING)

    def edit_it():
        porcupine.open_file(os.path.join(dirs.configdir, 'filetypes.ini'))
        _dialog.withdraw()

    button = ttk.Button(langspec, text="Edit filetypes.ini", command=edit_it)
    button.pack(anchor='center', **PADDING)


if __name__ == '__main__':
    from porcupine import _logs

    root = tk.Tk()
    root.withdraw()
    config.load()
    _logs.setup(verbose=True)

    init(root)
    show()

    # make the ok button and close button quit everything
    (_dialog.winfo_children()[0].winfo_children()[-1].winfo_children()[0]
     ['command']) = root.destroy
    _dialog.protocol('WM_DELETE_WINDOW', root.destroy)

    # the dialog is usable only if we get here, so we don't need to
    # wrap the whole thing in try/finally
    try:
        root.mainloop()
    finally:
        config.save()
