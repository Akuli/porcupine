import teek as tk

from porcupine import get_tab_manager, utils

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


# this widget is kind of weird
class LabelWithEmptySpaceAtLeft(tk.Label):

    def __init__(self, master):
        self._spacer = tk.Frame(master)
        self._spacer.pack(side='left', expand=True)
        super().__init__(master)
        self.pack(side='left')

    # i don't want to override destroy() because pythotk can call it too
    def destroy_me(self):
        self._spacer.destroy()
        self.destroy()


class StatusBar(tk.Frame):

    def __init__(self, master, tab):
        super().__init__(master)
        self.tab = tab
        # one label for each tab-separated thing
        self.labels = [tk.Label(self)]
        self.labels[0].pack(side='left')

        tab.on_status_changed.connect(self.update)
        self.update()

    # don't do this in tkinter, it has its own method called update
    def update(self):
        parts = self.tab.status.split('\t')
        assert len(parts) != 0

        # there's always at least one part, the label added in
        # __init__ is not destroyed here
        while len(self.labels) > len(parts):
            self.labels.pop().destroy_me()
        while len(self.labels) < len(parts):
            self.labels.append(LabelWithEmptySpaceAtLeft(self))

        for label, text in zip(self.labels, parts):
            label.config['text'] = text


def on_new_tab(tab):
    StatusBar(tab.bottom_frame, tab).pack(side='bottom', fill='x')


def setup():
    get_tab_manager().on_new_tab.connect(on_new_tab)
