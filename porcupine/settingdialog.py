"""A dialog for changing the settings."""

import codecs
import os
import re
import tkinter as tk
from tkinter import messagebox
import tkinter.font as tkfont

from porcupine.settings import config, reset_config

_PADDING = {'padx': 5, 'pady': 2}


def _create_checkbox(parent, *, text='', **kwargs):
    """Create a widget like like tk.Checkbutton.

    Unlike tk.Checkbutton, this doesn't screw up with dark GTK+ themes.
    tk.Checkbutton displays a white checkmark on a white background on
    my dark GTK+ 2 theme.
    """
    # I'm aware of ttk.Checkbutton, but ttk widgets display a light-gray
    # background on my dark GTK+ theme.

    # we can't use the checkbutton's text because the colors of the text
    # also change when the checkmark colors are changed :(
    frame = tk.Frame(parent)
    checkbox = tk.Checkbutton(frame, foreground='black',
                              selectcolor='white', **kwargs)
    checkbox.pack(side='left')
    label = tk.Label(frame, text=text)
    label.pack(side='right', fill='both', expand=True)

    # now we need to make the label behave like a part of the checkbox
    def redirect_events(event_string):
        def callback(event):
            checkbox.event_generate(event_string)
        label.bind(event_string, callback)

    redirect_events('<Button-1>')
    redirect_events('<Enter>')
    redirect_events('<Leave>')

    # the checkbox isn't easy to access, but it doesn't matter for this
    return frame


class _Section(tk.LabelFrame):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._row = 0
        self.grid_columnconfigure(0, weight=1)

    def add_widget(self, widget, text=None):
        if text is None:
            widget.grid(row=self._row, column=0, columnspan=2,
                        sticky='w', **_PADDING)
        else:
            label = tk.Label(self, text=text)
            label.grid(row=self._row, column=0, sticky='w', **_PADDING)
            widget.grid(row=self._row, column=1, sticky='w', **_PADDING)
        self._row += 1

    def add_checkbox(self, key, **kwargs):
        checkbox = _create_checkbox(self, variable=config[key], **kwargs)
        self.add_widget(checkbox)

    def add_entry(self, key, *, text, validator=None, **kwargs):
        if validator is None:
            entry = tk.Entry(self, textvariable=config[key])
            self.add_widget(entry, text)
        else:
            self._add_validating_entry(key, text, validator, **kwargs)

    def _add_validating_entry(self, key, text, validator, *,
                              _image_cache=[], **kwargs):
        var = tk.StringVar()
        var.set(config[key].get())

        if _image_cache:
            triangle_image, empty_image = _image_cache
        else:
            here = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(here, 'images', 'triangle.png')
            triangle_image = tk.PhotoImage(file=path)
            empty_image = tk.PhotoImage(
                width=triangle_image.width(),
                height=triangle_image.height())
            _image_cache[:] = [triangle_image, empty_image]

        frame = tk.Frame(self)
        entry = tk.Entry(frame, textvariable=var, **kwargs)
        entry.pack(side='left', fill='both', expand=True)
        trianglelabel = tk.Label(frame, width=20, image=empty_image)
        trianglelabel.pack(side='right')

        def to_config(*junk):
            value = var.get()
            if validator(value):
                trianglelabel['image'] = empty_image
                config[key].set(value)
            else:
                trianglelabel['image'] = triangle_image

        def from_config(*junk):
            var.set(config[key].get())

        var.trace('w', to_config)
        config[key].trace('w', from_config)
        self.add_widget(frame, text)

    def add_spinbox(self, key, *, text, **kwargs):
        var = tk.StringVar()
        var.set(str(config[key].get()))
        spinbox = tk.Spinbox(self, textvariable=var, **kwargs)

        def to_config(*junk):
            try:
                value = int(var.get())
            except ValueError:
                return
            if spinbox['from'] <= value <= spinbox['to']:
                config[key].set(value)

        def from_config(*junk):
            var.set(str(config[key].get()))

        var.trace('w', to_config)
        config[key].trace('w', from_config)
        self.add_widget(spinbox, text)


def _validate_font(string):
    # the editor crashes if the font is set to ''
    if not string:
        return False

    # This returns True for strings like 'asdfasdfasdf', but font
    # strings like that actually work so it's not a problem. tkfont.Font
    # also takes an exists keyword argument, but it makes it raise
    # errors way too often for this.
    try:
        tkfont.Font(font=string)
        return True
    except tk.TclError:
        return False


def _validate_encoding(name):
    try:
        codecs.lookup(name)
        return True
    except LookupError:
        return False


def _validate_geometry(geometry):
    """Check if a tkinter geometry is valid.

    >>> _validate_geometry('100x200+300+400')
    True
    >>> _validate_geometry('100x200')
    True
    >>> _validate_geometry('+300+400')
    True
    >>> _validate_geometry('asdf')
    False
    >>> # tkinter actually allows '', but it does nothing
    >>> _validate_geometry('')
    False
    """
    if not geometry:
        return False
    return re.search(r'^(\d+x\d+)?(\+\d+\+\d+)?$', geometry) is not None


class SettingDialog(tk.Toplevel):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.on_close = self.destroy
        self.protocol('WM_DELETE_WINDOW', self._close_me)

        filesection = self._create_filesection()
        editingsection = self._create_editingsection()
        guisection = self._create_guisection()
        separator = tk.Frame(self, height=3, border=1, relief='sunken')
        buttonframe = self._create_buttons()

        for widget in [filesection, editingsection, guisection,
                       separator, buttonframe]:
            widget.pack(fill='x', **_PADDING)

    def _close_me(self):
        """Call self.on_close().

        This is needed because it's possible to set on_close to another
        callback function after creating the SettingDialog.
        """
        self.on_close()

    def _create_filesection(self):
        section = _Section(self, text="Files")
        section.add_entry(
            'files:encoding', validator=_validate_encoding,
            text="Encoding of opened and saved files:")
        section.add_checkbox(
            'files:add_trailing_newline',
            text="Make sure that files end with an empty line when saving")
        return section

    def _create_editingsection(self):
        section = _Section(self, text="Editing")
        section.add_entry(
            'editing:font', validator=_validate_font,
            text=('The font as a Tkinter font string ' +
                  '(e.g. "{Some Font} 12"):'))
        section.add_spinbox(
            'editing:indent', from_=1, to=100, text="Indent width:")
        section.add_checkbox(
            'editing:undo', text="Enable undo and redo")
        section.add_checkbox(
            'editing:autocomplete', text="Autocomplete with tab")
        return section

    def _create_guisection(self):
        section = _Section(self, text="The GUI")
        section.add_checkbox(
            'gui:linenumbers', text="Display line numbers")
        section.add_checkbox(
            'gui:statusbar', text="Display a statusbar at bottom")
        section.add_entry(
            'gui:default_geometry', validator=_validate_geometry,
            text=("Default window size as a Tkinter geometry " +
                  "(e.g. 650x500):"))
        return section

    def _create_buttons(self):
        frame = tk.Frame(self)
        ok = tk.Button(frame, width=6, text="OK", command=self._close_me)
        ok.pack(side='right', **_PADDING)
        reset = tk.Button(frame, width=6, text="Reset", command=self.reset)
        reset.pack(side='right', **_PADDING)
        return frame

    def reset(self):
        confirmed = messagebox.askyesno(
            "Reset Settings", "Do you want to reset all settings to defaults?",
            parent=self)
        if not confirmed:
            return

        reset_config()
        messagebox.showinfo(
            "Reset Settings", "All settings were reset to defaults.",
            parent=self)


if __name__ == '__main__':
    import porcupine.settings

    root = tk.Tk()
    root.withdraw()

    porcupine.settings.load()
    dialog = SettingDialog()
    dialog.title("Porcupine Settings")
    dialog.on_close = root.destroy

    # the dialog is usable only if we get here, so we don't need to wrap
    # the whole thing in try/finally
    try:
        root.mainloop()
    finally:
        porcupine.settings.save()
