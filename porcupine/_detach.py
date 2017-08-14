import tkinter as tk


class Detacher:

    def __init__(self, frame):
        self._frame = frame

        self._help_windows = {}   # {key: (help_window, width, height)}
        for key, text in [
                ('detach', "Drop the tab here\nto detach it..."),
                ('attach', "Drop the tab here to\nattach it back...")]:
            window = tk.Toplevel()
            window.withdraw()
            window.overrideredirect(True)

            label = tk.Label(window, fg='black', bg='#ffff99',
                             padx=5, pady=5, text=text)
            label.pack()

            self._help_windows[key] = (
                window, label.winfo_reqwidth(), label.winfo_reqheight())

    def on_drag(self, event):
        """Bind some widget's <Button1-Motion> to this."""
        main_window = self._frame.winfo_toplevel()
        help_window, width, height = self._help_windows['detach']

        # event.x_root and event.y_root are relative to the whole
        # screen, these are relative to the window
        mouse_x = event.x_root - main_window.winfo_x()
        mouse_y = event.y_root - main_window.winfo_y()

        if (0 < mouse_x < main_window.winfo_width() and
                0 < mouse_y < main_window.winfo_height()):
            help_window.withdraw()
        else:
            x = event.x_root - width//2     # noqa  # centered
            y = event.y_root - height - 10     # 10px above cursor
            help_window.deiconify()
            help_window.geometry('+%d+%d' % (x, y))

    def on_drop(self, event):
        """Bind some widget's <ButtonRelease-1> to this."""
        help_window, *size = self._help_windows['detach']
        if help_window.state() != 'withdrawn':
            self.detach(event.x_root, event.y_root)

    def detach(self, x, y):
        """Pop off the window.

        The window is centered on x and y, treated as relative to the whole
        screen. Usually they come from a mouse event's x_root and y_root.
        """
        help_window, *size = self._help_windows['detach']
        help_window.withdraw()

        # only toplevels and root windows have wm methods :(
        window = self._frame.winfo_toplevel()   # must be before the wm manage
        self._frame.tk.call('wm', 'manage', self._frame)

        # center the detached window on the main window
        width, height = 400, 300      # TODO: don't hard-code this
        left = max(x - width//2, 0)       # noqa
        top = max(y - height//2, 0)      # noqa
        self._frame.tk.call('wm', 'geometry', self._frame,
                            '{}x{}+{}+{}'.format(width, height, left, top))

    def attach(self):
        """Undo a detach()."""
        self._frame.tk.call('wm', 'forget', self._frame)


if __name__ == '__main__':
    class ExampleDetacher(Detacher):

        def __init__(self, frame, dragger):
            super().__init__(frame)
            self._dragger = dragger
            self._dragger['text'] = "Drag me somewhere..."

        def detach(self, *args):
            print("detaching")
            super().detach(*args)
            self._dragger['text'] = "Now it's detached!"

            # examples of other customizations: change title and make
            # the closing button attach the frame back
            self._frame.tk.call('wm', 'title', self._frame, "Detached Frame")
            self._frame.tk.call(
                'wm', 'protocol', self._frame, 'WM_DELETE_WINDOW',
                self._frame.register(self.attach))

        def attach(self):
            print("attaching")
            super().attach()
            self._frame.pack()
            self._dragger['text'] = "Drag me somewhere..."

    root = tk.Tk()

    frame = tk.Frame()
    frame.pack()
    text = tk.Text(frame, width=50, height=15)
    text.insert("end", "bla bla bla")
    text.pack()

    dragger = tk.Label(root, padx=10, pady=10, border=1, relief='raised')
    dragger.pack()

    detacher = ExampleDetacher(frame, dragger)
    dragger.bind('<Button1-Motion>', detacher.on_drag)
    dragger.bind('<ButtonRelease-1>', detacher.on_drop)

    root.mainloop()
