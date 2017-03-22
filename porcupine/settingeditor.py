"""A dialog for changing the settings."""
# This uses ttk widgets instead of tk widgets because it needs
# ttk.Combobox anyway and mixing the widgets looks inconsistent.

import base64
import pkgutil
import re
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

from porcupine.settings import config

_PADDING = {'padx': 5, 'pady': 2}


try:
    # There's no ttk.Spinbox for some reason. Maybe this will be fixed
    # later?
    TtkSpinbox = ttk.Spinbox
except AttributeError:
    # At least not yet, but implementing this is easy to do by reading
    # the code of ttk.Combobox.
    class TtkSpinbox(ttk.Entry):
        def __init__(self, master=None, *, from_=None, **kwargs):
            if from_ is not None:
                kwargs['from'] = from_  # this actually works
            super().__init__(master, 'ttk::spinbox', **kwargs)


def _list_families():
    result = {'TkFixedFont'}   # a set to delete duplicates
    for family in tkfont.families():
        # There are some weird fonts starting with @ on Windows for some
        # reason.
        if not family.startswith('@'):
            result.add(family)
    return sorted(result, key=str.casefold)


class _WarningTriangle(ttk.Label):

    _triangle_image = None

    def __init__(self, *args, **kwargs):
        if self._triangle_image is None:
            data = pkgutil.get_data('porcupine', 'images/triangle.png')
            type(self)._triangle_image = tk.PhotoImage(
                data=base64.b64encode(data))

        super().__init__(*args, **kwargs)
        self.hide()

    def show(self):
        self['image'] = type(self)._triangle_image

    def hide(self):
        self['image'] = ''


class _Section(ttk.LabelFrame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.row = 0
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, minsize=20)

    def add_widget(self, widget, label=None, triangle=None):
        if label is None:
            widget.grid(row=self.row, column=0, columnspan=2,
                        sticky='w', **_PADDING)
        else:
            if isinstance(label, str):
                label = ttk.Label(self, text=label)
            label.grid(row=self.row, column=0, sticky='w', **_PADDING)
            widget.grid(row=self.row, column=1, sticky='e', **_PADDING)
        if triangle is not None:
            triangle.grid(row=self.row, column=2)
        self.row += 1

    # these methods add widgets that change the settings and also change
    # when something else changes the settings, e.g. the reset button

    def add_checkbox(self, key, **kwargs):
        var = tk.BooleanVar()
        checkbox = ttk.Checkbutton(self, variable=var, **kwargs)
        self.add_widget(checkbox)

        def from_config(*junk):
            var.set(config[key])

        def to_config(*junk):
            config[key] = var.get()

        config.connect(key, from_config)
        from_config()
        var.trace('w', to_config)
        return checkbox   # see long line marker

    def add_entry(self, key, *, label, **kwargs):
        var = tk.StringVar()
        var.set(config[key])
        entry = ttk.Entry(self, textvariable=var, **kwargs)
        triangle = _WarningTriangle(self)

        def to_config(*junk):
            value = var.get()
            if config.validate(key, value):
                triangle.hide()
                config[key] = value
            else:
                triangle.show()

        def from_config(key, value):
            var.set(value)

        var.trace('w', to_config)
        config.connect(key, from_config)
        self.add_widget(entry, label, triangle)

    def add_spinbox(self, key, *, label, **kwargs):
        var = tk.StringVar()
        var.set(str(config[key]))
        spinbox = TtkSpinbox(self, textvariable=var, **kwargs)
        triangle = _WarningTriangle(self)

        def to_config(*junk):
            try:
                value = int(var.get())
                if not config.validate(key, value):
                    raise ValueError
            except ValueError:
                triangle.show()
                return
            triangle.hide()
            config[key] = value

        def from_config(key, value):
            var.set(str(value))

        var.trace('w', to_config)
        config.connect(key, from_config)
        self.add_widget(spinbox, label, triangle)
        return spinbox   # see long line marker

    def add_font_selector(self, key, *, label, **kwargs):
        # Tk uses 'TkFixedFont' as a default font, but it doesn't
        # support specifying a size. The size variable gets a stupid
        # default here, but another value may be read from config.
        familyvar = tk.StringVar()
        sizevar = tk.StringVar(value='10')

        frame = ttk.Frame(self)
        family_combobox = ttk.Combobox(
            frame, textvariable=familyvar, values=_list_families())
        family_combobox['width'] -= 4  # not much bigger than other widgets
        family_combobox.pack(side='left')
        size_spinbox = TtkSpinbox(frame, textvariable=sizevar,
                                  from_=1, to=100, width=4)
        size_spinbox.pack(side='left')
        triangle = _WarningTriangle(self)

        def from_config(key, value):
            # the fonts are stored as "{family} size" strings because
            # tkinter widgets can use strings like that, but the default
            # font is 'TkFixedFont' because it does not support
            # specifying a size
            if value == 'TkFixedFont':
                familyvar.set('TkFixedFont')
            else:
                match = re.search(r'^\{(.+)\} (\d+)$', value)
                familyvar.set(match.group(1))
                sizevar.set(match.group(2))

        def to_config(*junk):
            if familyvar.get() == 'TkFixedFont':
                size_spinbox['state'] = 'disabled'
                config[key] = 'TkFixedFont'
                triangle.hide()
                return

            size_spinbox['state'] = 'normal'
            value = '{%s} %s' % (familyvar.get(), sizevar.get())
            if config.validate(key, value):
                triangle.hide()
                config[key] = value
            else:
                triangle.show()

        familyvar.trace('w', to_config)
        sizevar.trace('w', to_config)
        config.connect(key, from_config)
        from_config(key, config[key])
        self.add_widget(frame, label, triangle)


class SettingEditor(ttk.Frame):

    def __init__(self, *args, ok_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._ok_callback = ok_callback

        filesection = self._create_filesection()
        editingsection = self._create_editingsection()
        guisection = self._create_guisection()
        separator = ttk.Separator(self)
        buttonframe = self._create_buttons()

        for widget in [filesection, editingsection, guisection,
                       separator, buttonframe]:
            widget.pack(fill='x', **_PADDING)

    def _create_filesection(self):
        section = _Section(self, text="Files")
        section.add_entry(
            'files:encoding', label="Encoding of opened and saved files:")
        section.add_checkbox(
            'files:add_trailing_newline',
            text="Make sure that files end with an empty line when saving")
        return section

    def _add_long_line_marker(self, section):
        checkbox = section.add_checkbox(
            'editing:longlinemarker',
            text="Display a long line marker at this column:")
        section.row -= 1    # overwrite same row again
        spinbox = section.add_spinbox('editing:maxlinelen', from_=1, to=200,
                                      label=checkbox)

        def on_check(key, value):
            if value:
                spinbox['state'] = 'normal'
            else:
                spinbox['state'] = 'disabled'

        config.connect('editing:longlinemarker', on_check)

    def _create_editingsection(self):
        section = _Section(self, text="Editing")
        section.add_font_selector(
            'editing:font', label="Font family and size:")
        section.add_spinbox(
            'editing:indent', from_=1, to=100, label="Indent width:")
        section.add_checkbox(
            'editing:undo', text="Enable undo and redo")
        section.add_checkbox(
            'editing:autocomplete', text="Autocomplete with tab")
        self._add_long_line_marker(section)
        return section

    def _create_guisection(self):
        section = _Section(self, text="The GUI")
        section.add_checkbox(
            'gui:linenumbers', text="Display line numbers")
        section.add_checkbox(
            'gui:statusbar', text="Display a statusbar at bottom")
        section.add_entry(
            'gui:default_geometry',
            label="Default window size as a Tkinter geometry (e.g. 650x500):")
        return section

    def _create_buttons(self):
        frame = ttk.Frame(self)

        okbutton = ttk.Button(frame, width=6, text="OK")
        okbutton.pack(side='right', **_PADDING)
        if self._ok_callback is not None:
            okbutton['command'] = self._ok_callback
        resetbutton = ttk.Button(
            frame, width=6, text="Reset", command=self.reset)
        resetbutton.pack(side='right', **_PADDING)

        return frame

    def reset(self):
        confirmed = messagebox.askyesno(
            "Reset settings", "Do you want to reset all settings to defaults?",
            parent=self)
        if confirmed:
            config.reset()
            messagebox.showinfo(
                "Reset settings", "All settings were reset to defaults.",
                parent=self)


if __name__ == '__main__':
    import porcupine.settings

    root = tk.Tk()
    porcupine.settings.load()

    settingedit = SettingEditor(root, ok_callback=root.destroy)
    settingedit.pack(fill='both', expand=True)

    root.title("Porcupine Settings")
    try:
        # the dialog is usable only if we get here, so we don't need to
        # wrap the whole thing in try/finally
        root.mainloop()
    finally:
        porcupine.settings.save()
