#!/usr/bin/env python3

# Copyright (c) 2017 Akuli

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""A find dialog."""

# TODO: replace support?

import tkinter as tk


def _parse_geometry(geometry):
    """Convert tkinter geometry string to (x, y, width, height) tuple."""
    place, x, y = geometry.split('+')
    width, height = map(int, place.split('x'))
    return int(x), int(y), width, height


class FindDialog(tk.Toplevel):

    def __init__(self, editor, **kwargs):
        super().__init__(editor, **kwargs)
        self.editor = editor

        topframe = tk.Frame(self)
        topframe.pack(expand=True, anchor='center')
        label = tk.Label(topframe, text="What do you want to search for?")
        label.pack()
        self.entry = tk.Entry(topframe)
        self.entry.bind('<Return>', lambda event: self.find())
        self.entry.bind('<Escape>', lambda event: self.withdraw())
        self.entry.pack()
        self.notfoundlabel = tk.Label(self, fg='red')
        self.notfoundlabel.pack()
        buttonframe = tk.Frame(self)
        buttonframe.pack(side='bottom', fill='x')

        closebutton = tk.Button(buttonframe, text="Close this dialog",
                                command=self.withdraw)
        closebutton.pack(side='right')
        findbutton = tk.Button(buttonframe, text="Find", command=self.find)
        findbutton.pack(side='right')

        self.entry.focus()
        self.title("Find")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.protocol('WM_DELETE_WINDOW', self.withdraw)

    def show(self):
        self.deiconify()
        self.update_idletasks()   # wait for it to get full size
        editorx, editory, editorwidth, editorheight = _parse_geometry(
            self.editor.geometry())
        width, height = 240, 120
        x = editorx + (editorwidth - width) // 2
        y = editory + (editorheight - height) // 2
        self.geometry('%dx%d+%d+%d' % (width, height, x, y))

    def find(self, what=None):
        self.notfoundlabel['text'] = ''
        text = self.editor.textwidget
        if what is None:
            what = self.entry.get()
            if not what:
                # the user didnt enter anything
                return
        start = text.search(what, 'insert+1c')
        if start:
            end = start + ('+%dc' % len(what))
            text.tag_remove('sel', '0.0', 'end')
            text.tag_add('sel', start, end)
            text.mark_set('insert', start)
            text.see(start)
        else:
            self.notfoundlabel['text'] = "Search string not found :("
