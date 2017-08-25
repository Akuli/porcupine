# Old Porcupines used to have tabs that could be dragged out of the main
# editing window, and then it was possible to edit files in a separate
# window. See the "wm manage" command in wm(3tk) for an explanation
# about how this works.
#
# Detaching tabs didn't work that well for a few reasons:
#   - Plugins relied on tabmanager.current_tab, but it didn't update
#     when the user selected a detached window. (This could probably be
#     fixed easily by binding the tab's <FocusIn> event.)
#   - The detached tabs were limited in several ways, not full-featured
#     Porcupines.
#   - The "wm manage" command that everything is based on doesn't work
#     with ttk widgets.
#
# Anyway, this file contains the implementation that Porcupine used for
# detaching tabs. There's a small demo at the bottom, so you can just
# run this file in Python.


import functools
import tkinter as tk


def _mouse_is_on(widget):
    # all coordinates are relative to the screen
    x, y = widget.winfo_pointerxy()
    left = widget.winfo_rootx()
    top = widget.winfo_rooty()
    right = left + widget.winfo_width()
    bottom = top + widget.winfo_height()
    return left < x < right and top < y < bottom


class Detacher:

    def __init__(self, labelframe: tk.LabelFrame):
        self.labelframe = labelframe
        self._main_window = labelframe.winfo_toplevel()   # type: tk.Widget

        self._help_windows = {}   # {key: (help_window, width, height)}
        for key, text in [
                ('detach', "Drop the tab here\nto detach it..."),
                ('attach', "Drop the tab here\nto attach it back...")]:
            window = tk.Toplevel()
            window.withdraw()
            window.overrideredirect(True)

            label = tk.Label(window, fg='black', bg='#ffff99',
                             padx=5, pady=5, text=text)
            label.pack()

            self._help_windows[key] = (
                window, label.winfo_reqwidth(), label.winfo_reqheight())

    # because explicit is better than implicit
    def _get_help_window(self, key) -> tk.Toplevel:
        return self._help_windows[key][0]

    def _on_drag(self, key, event):
        help_window, width, height = self._help_windows[key]

        if key == 'detach':
            # dragging anywhere outside the main window is ok
            ready2go = (not _mouse_is_on(self._main_window))
        else:
            # ideally this would check if the labelframe is on top of a
            # visible part of the main window, but this is fine for now
            assert key == 'attach'
            ready2go = (_mouse_is_on(self._main_window) and
                        not _mouse_is_on(self.labelframe))

        if ready2go:
            x = event.x_root - width//2      # centered    # noqa
            y = event.y_root - height - 10   # 10px above cursor
            help_window.deiconify()
            help_window.geometry('+%d+%d' % (x, y))
        else:
            help_window.withdraw()

    on_detaching_drag = functools.partialmethod(_on_drag, 'detach')
    on_attaching_drag = functools.partialmethod(_on_drag, 'attach')

    def on_detaching_drop(self, event):
        """Bind some widget's <ButtonRelease-1> to this."""
        if self._get_help_window('detach').state() != 'withdrawn':
            self._get_help_window('detach').withdraw()
            self.detach(event.x_root, event.y_root)

    def on_attaching_drop(self, event):
        """Bind some widget's <ButtonRelease-1> to this when detached."""
        if self._get_help_window('attach').state() != 'withdrawn':
            self._get_help_window('attach').withdraw()
            self.attach()

    def detach(self, x, y):
        """Pop off the window.

        The window is centered on x and y, treated as relative to the whole
        screen. Usually they come from a mouse event's x_root and y_root.
        """
        # only toplevels and root windows have wm methods :(
        self.labelframe.tk.call('wm', 'manage', self.labelframe)
        self.labelframe.tk.call('wm', 'deiconify', self.labelframe)

        # center the detached window on the cursor
        # there's a bit more borders than winfo_reqstuff says, 100 is
        # more than enough but making it a bit bigger doesn't hurt
        width = max(self.labelframe.winfo_reqwidth() + 100, 400)
        height = max(self.labelframe.winfo_reqheight() + 100, 300)
        left = max(x - width//2, 0)       # noqa
        top = max(y - height//2, 0)       # noqa
        self.labelframe.tk.call('wm', 'geometry', self.labelframe,
                                '%dx%d+%d+%d' % (width, height, left, top))

    def attach(self):
        """Undo a detach()."""
        self.labelframe.tk.call('wm', 'forget', self.labelframe)


if __name__ == '__main__':
    # example usage
    class ExampleDetacher(Detacher):

        def __init__(self, labelframe):
            super().__init__(labelframe)

            # hide the fact that it's a label frame
            self.labelframe['border'] = 0

        def detach(self, *args):
            print("detaching")
            super().detach(*args)

            top_label = tk.Label(
                self.labelframe, padx=10, pady=5, relief='sunken',
                text="Drag this back to the main window")
            top_label.bind('<Button1-Motion>', self.on_attaching_drag)
            top_label.bind('<ButtonRelease-1>', self.on_attaching_drop)

            labelframe['border'] = 2
            labelframe['labelwidget'] = top_label

            self.labelframe.tk.call(
                'wm', 'title', self.labelframe, "Detached Tab")
            self.labelframe.tk.call(
                'wm', 'protocol', self.labelframe, 'WM_DELETE_WINDOW',
                self.labelframe.register(self.attach))

        def attach(self):
            print("attaching")
            super().attach()
            self.labelframe['border'] = 0
            self.labelframe['labelwidget'] = ''
            self.labelframe.pack()

    root = tk.Tk()

    labelframe = tk.LabelFrame(border=0)
    labelframe.pack()
    text = tk.Text(labelframe, width=50, height=15)
    text.insert("end", "bla bla bla")
    text.pack()

    dragger = tk.Label(root, text="Drag this label somewhere...",
                       padx=10, pady=10, border=1, relief='raised')
    dragger.pack()

    detacher = ExampleDetacher(labelframe)
    dragger.bind('<Button1-Motion>', detacher.on_detaching_drag)
    dragger.bind('<ButtonRelease-1>', detacher.on_detaching_drop)

    root.mainloop()
