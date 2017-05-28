"""A dialog for changing the settings."""
# This uses ttk widgets instead of tk widgets because it needs
# ttk.Combobox anyway and mixing the widgets looks inconsistent.
# TODO: some nice API for plugins to add stuff

import re
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.font as tkfont

from porcupine import utils
from porcupine.settings import config, InvalidValue

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

_PADDING = {'padx': 5, 'pady': 2}


class _ConfigMixin:

    def __init__(self, sectionwidget, **kwargs):
        super().__init__(sectionwidget, **kwargs)
        self._triangle = ttk.Label(sectionwidget)

    def show_triangle(self):
        """Add a triangle image next to the widget.

        This does nothing if the triangle is already visible.
        """
        self._triangle['image'] = utils.get_image('triangle.gif')

    def hide_triangle(self):
        """Hide the triangle image if it's visible."""
        # setting the image to None doesn't work, but setting to '' does
        self._triangle['image'] = ''

    def add(self, label=None):
        """Grid this widget correctly to the section widget.

        The label can be None, a string or a Ttk widget. If it's a
        string, a new ``ttk.Label`` will be created.
        """
        if label is None:
            self.grid(row=self.master._row, column=0,
                      columnspan=2, sticky='w', **_PADDING)
        else:
            if isinstance(label, str):
                label = ttk.Label(self.master, text=label)
            label.grid(row=self.master._row, column=0, sticky='w', **_PADDING)
            self.grid(row=self.master._row, column=1, sticky='e', **_PADDING)
        self._triangle.grid(row=self.master._row, column=2)
        self.master._row += 1


class Checkbutton(_ConfigMixin, ttk.Checkbutton):

    def __init__(self, sectionwidget, configkey, **kwargs):
        super().__init__(sectionwidget, **kwargs)
        self._key = configkey
        self._var = self['variable'] = tk.BooleanVar()
        self._var.trace('w', self._to_config)
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        config[self._key] = self._var.get()


class Entry(_ConfigMixin, ttk.Entry):

    def __init__(self, sectionwidget, configkey, **kwargs):
        super().__init__(sectionwidget, **kwargs)
        self._key = configkey
        self._var = self['textvariable'] = tk.StringVar()
        self._var.trace('w', self._to_config)
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        try:
            config[self._key] = self._var.get()
            self.hide_triangle()
        except InvalidValue:
            self.show_triangle()


class Spinbox(_ConfigMixin, _TtkSpinbox):

    def __init__(self, sectionwidget, configkey, **kwargs):
        super().__init__(sectionwidget, **kwargs)
        self._key = configkey
        self._var = self['textvariable'] = tk.StringVar()
        self._var.trace('w', self._to_config)

        # self._var.set() will be called with an integer, but tkinter
        # str()s it because everything is a string in Tcl
        config.connect(*configkey, callback=self._var.set, run_now=True)

    def _to_config(self, *junk):
        try:
            config[self._key] = int(self._var.get())
            self.hide_triangle()
        except (ValueError, InvalidValue):
            self.show_triangle()


class FontSelector(_ConfigMixin, ttk.Frame):

    def __init__(self, parentwidget, section, **kwargs):
        super().__init__(parentwidget, **kwargs)
        self._section = section

        self._familyvar = tk.StringVar()
        self._sizevar = tk.StringVar()
        familycombo = ttk.Combobox(self, textvariable=self._familyvar,
                                   width=15, values=self._get_families())
        familycombo.pack(side='left')
        size_spinbox = _TtkSpinbox(
            self, from_=3, to=1000, width=4, textvariable=self._sizevar)
        size_spinbox.pack(side='left')

        config.connect(section, 'family', self._familyvar.set, run_now=True)
        config.connect(section, 'size', self._sizevar.set, run_now=True)
        self._familyvar.trace('w', self._to_config)
        self._sizevar.trace('w', self._to_config)

        # _family2config and _size2config can't just call show_triangle()
        # because it must be hidden if e.g. size is ok but family is not
        self._family_ok = self._size_ok = True

    @staticmethod
    def _get_families():
        # delete duplicates, sort and get weird of weird fonts starting
        # with @ on windows
        result = [family for family in tkfont.families() if family[0] != '@']
        return sorted(set(result))

    # this is combined into one function because otherwise figuring out
    # when to show the triangle would be harder
    def _to_config(self, *junk):
        try:
            config[self._section, 'family'] = self._familyvar.get()
            config[self._section, 'size'] = int(self._sizevar.get())
            self.hide_triangle()
        except (ValueError, InvalidValue):
            self.show_triangle()


class SettingEditor(ttk.Frame):

    def __init__(self, *args, ok_callback=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sections = {}

        filesection = self._create_file_section()
        editingsection = self._create_editing_section()
#        guisection = self._create_guisection()
        buttonframe = self._create_buttons(ok_callback)

        for widget in [filesection, editingsection]:# guisection
            widget.pack(fill='x', **_PADDING)
        self._create_buttons(ok_callback).pack(side='bottom', fill='x')
        ttk.Separator(self).pack(side='bottom', fill='x', **_PADDING)

    def get_section(self, title):
        try:
            return self._sections[title]
        except KeyError:
            section = ttk.LabelFrame(self, text=title)
            section._row = 0     # see _ConfigMixin.add
            section.grid_columnconfigure(0, weight=1)
            section.grid_columnconfigure(2, minsize=20)
            self._sections[title] = section
            return section

    def _create_file_section(self):
        section = self.get_section("Files")
        entry = Entry(section, ('Files', 'encoding'))
        entry.add("Encoding of opened and saved files:")
        checkbox = Checkbutton(
            section, ('Files', 'add_trailing_newline'),
            text="Make sure that files end with an empty line when saving")
        checkbox.add()
        return section

    def _create_editing_section(self):
        section = self.get_section("Editing")
        font_selector = FontSelector(section, 'Font')
        font_selector.add("The font:")
        indent_spinbox = Spinbox(
            section, ('Editing', 'indent'), from_=1, to=100)
        indent_spinbox.add("Indent size:")
        undo_checkbox = Checkbutton(
            section, ('Editing', 'undo'), text="Enable undo and redo")
        undo_checkbox.add()
        return section

    def _create_guisection(self):
        section = __Section(self, text="The GUI")
        section.add_checkbox(
            'gui:linenumbers', text="Display line numbers")
        section.add_checkbox(
            'gui:statusbar', text="Display a statusbar at bottom")
        section.add_entry(
            'gui:default_geometry',
            label="Default window size as a Tkinter geometry (e.g. 650x500):")
        return section

    def _create_buttons(self, ok_callback):
        frame = ttk.Frame(self)

        okbutton = ttk.Button(frame, width=6, text="OK")
        okbutton.pack(side='right', **_PADDING)
        if ok_callback is not None:
            okbutton['command'] = ok_callback
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
                "Reset settings", "All settings were set to defaults.",
                parent=self)


_dialog = None


def show(parentwindow):
    global _dialog
    if _dialog is None:
        _dialog = tk.Toplevel()
        editor = SettingEditor(_dialog, ok_callback=_dialog.withdraw)
        editor.pack(fill='both', expand=True)

        _dialog.title("Porcupine Settings")
        _dialog.update()
        _dialog.minsize(_dialog.winfo_reqwidth(), _dialog.winfo_reqheight())

    _dialog.transient(parentwindow)
    _dialog.deiconify()


if __name__ == '__main__':
    from porcupine import settings

    root = tk.Tk()
    root.withdraw()
    settings.load()
    show(root)
    _dialog.withdraw = root.destroy       # lol

    try:
        # the dialog is usable only if we get here, so we don't need to
        # wrap the whole thing in try/finally
        root.mainloop()
    finally:
        settings.save()
