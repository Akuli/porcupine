from tkinter import ttk

import porcupine

# i have experimented with a logging handler that displays logging
# messages in the label, but it's not as good idea as it sounds like,
# not all INFO messages are something that users should see all the time


# this widget is kind of weird
class LabelWithEmptySpaceAtLeft(ttk.Label):

    def __init__(self, master):
        self._spacer = ttk.Frame(master)
        self._spacer.pack(side='left', expand=True)
        super().__init__(master)
        self.pack(side='left')

    def destroy(self):
        self._spacer.destroy()
        super().destroy()


class StatusBar(ttk.Frame):

    def __init__(self, tab):
        super().__init__(tab)
        # one label for each tab-separated thing
        self.labels = [ttk.Label(self)]
        self.labels[0].pack(side='left')

        tab.bind('<<StatusChanged>>', self.do_update, add=True)
        self.do_update()

    # this is do_update() because tkinter has a method called update()
    def do_update(self, junk=None):
        parts = self.master.status.split('\t')

        # there's always at least one part, the label added in
        # __init__ is not destroyed here
        while len(self.labels) > len(parts):
            self.labels.pop().destroy()
        while len(self.labels) < len(parts):
            self.labels.append(LabelWithEmptySpaceAtLeft(self))

        for label, text in zip(self.labels, parts):
            label['text'] = text


def on_new_tab(event):
    tab = event.widget.tabs[-1]
    StatusBar(tab).pack(side='bottom', fill='x')


def setup():
    porcupine.get_tab_manager().bind('<<NewTab>>', on_new_tab, add=True)
