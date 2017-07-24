"""Find/replace widget."""

import tkinter as tk

from porcupine import utils


class Finder(tk.Frame):
    """A widget for finding and replacing text.

    Use the pack geometry manager with this widget.
    """

    def __init__(self, parent, textwidget, **kwargs):
        super().__init__(parent, **kwargs)

        self.grid_columnconfigure(1, weight=1)
        self._textwidget = textwidget

        entrygrid = tk.Frame(self)
        entrygrid.grid(row=0, column=0)
        self._find_entry = self._add_entry(entrygrid, 0, "Find:", self.find)
        self._replace_entry = self._add_entry(entrygrid, 1, "Replace with:")

        buttonframe = tk.Frame(self)
        buttonframe.grid(row=1, column=0, sticky='we')
        buttons = [
            ("Find", self.find),
            ("Replace", self.replace),
            ("Replace and find", self.replace_and_find),
            ("Replace all", self.replace_all),
        ]
        for text, command in buttons:
            button = tk.Button(buttonframe, text=text, command=command)
            button.pack(side='left', fill='x', expand=True)

        # TODO: implement this full words only thing
        #self._full_words_var = tk.BooleanVar()
        #checkbox = utils.Checkbox(self, text="Full words only",
        #                          variable=self._full_words_var)
        #checkbox.grid(row=0, column=1, sticky='nw')

        self._statuslabel = tk.Label(self)
        self._statuslabel.grid(row=1, column=1, columnspan=2, sticky='nswe')

        closebutton = tk.Label(self, image=utils.get_image('closebutton.gif'))
        closebutton.grid(row=0, column=2, sticky='ne')
        closebutton.bind('<Button-1>', lambda event: self.pack_forget())

    def _add_entry(self, frame, row, text, callback=None):
        tk.Label(frame, text=text).grid(row=row, column=0)
        entry = tk.Entry(frame, width=35, font='TkFixedFont')
        entry.bind('<Escape>', lambda event: self.pack_forget())
        if callback is not None:
            entry.bind('<Return>', lambda event: callback())
        entry.grid(row=row, column=1, sticky='we')
        return entry

    # reset this when showing
    def pack(self, *args, **kwargs):
        self._statuslabel['text'] = ''
        self._find_entry.focus()
        super().pack(*args, **kwargs)

    def find(self):
        what = self._find_entry.get()
        if not what:
            self._statuslabel['text'] = "Cannot find an emptiness!"
            return

        start = self._textwidget.search(what, 'insert + 1 char')
        if start:
            self._statuslabel['text'] = ''
            end = '%s + %d chars' % (start, len(what))
            self._textwidget.tag_remove('sel', '1.0', 'end')
            self._textwidget.tag_add('sel', start, end)
            self._textwidget.mark_set('insert', start)
            self._textwidget.see(start)
        else:
            self._statuslabel['text'] = "I can't find it :("

    def replace(self):
        find_text = self._find_entry.get()
        if not find_text:
            self._statuslabel['text'] = "Cannot replace an emptiness!"
            return

        try:
            start, end = self._textwidget.tag_ranges('sel')
            if self._textwidget.index(start) == self._textwidget.index(end):
                # empty area selected
                raise ValueError
            if self._textwidget.get(start, end) != find_text:
                # wrong text selected
                raise ValueError
        except ValueError:
            self._statuslabel['text'] = "Click the find button first."
            return

        if self._textwidget.get(start, end) != self._find_entry.get():
            # old match, user needs to click the find button again
            return

        replace_text = self._replace_entry.get()
        self._textwidget.delete(start, end)
        self._textwidget.insert(start, replace_text)
        new_end = '%s + %d chars' % (start, len(replace_text))
        self._textwidget.tag_add('sel', start, new_end)

    def replace_and_find(self):
        self.replace()
        self.find()

    def replace_all(self):
        find_text = self._find_entry.get()
        replace_text = self._replace_entry.get()
        if not find_text:
            self._statuslabel['text'] = "Cannot replace an emptiness!"
            return

        start = '1.0'
        count = 0
        while True:
            start = self._textwidget.search(find_text, start, 'end')
            if not start:
                break

            end = '%s + %d chars' % (start, len(find_text))
            self._textwidget.delete(start, end)
            self._textwidget.insert(start, replace_text)
            start = '%s + %d chars' % (start, len(replace_text)+1)
            count += 1

        if count == 1:
            self._statuslabel['text'] = "Replaced 1 occurance."
        else:
            self._statuslabel['text'] = "Replaced %d occurances." % count


if __name__ == '__main__':
    from porcupine.settings import config
    root = tk.Tk()
    config.load()
    text = tk.Text(root)
    text.insert('1.0', 'asdf ' * 10)
    text.pack(fill='both', expand=True)
    finder = Finder(root, text)
    finder.pack(fill='x')
    root.mainloop()
