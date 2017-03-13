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

"""Run the editor."""

import argparse
import os
import sys
import tkinter as tk

import porcupine.editor


here = os.path.dirname(os.path.abspath(__file__))
default_config = os.path.join(here, 'default_config.ini')
user_config = os.path.join(os.path.expanduser('~'), '.porcupine.ini')


def main():
    parser = argparse.ArgumentParser(description=porcupine.__doc__)
    parser.add_argument(
        'file', nargs=argparse.ZERO_OR_MORE,
        help="open this file when the editor starts")
    args = parser.parse_args()

    root = tk.Tk()

    files = porcupine.config.read([default_config, user_config])
    if default_config not in files:
        print("porcupine.__main__: cannot read default_config.ini",
              file=sys.stderr)
        sys.exit(1)
    if user_config in files:
        print("porcupine.__main__: configuration was read from", user_config)

    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    for file in args.file:
        # the editor doesn't create new files when opening, so we need to
        # take care of that here
        if os.path.exists(file):
            editor.open_file(file)
        else:
            editor.open_file(file, content='')

    root['menu'] = editor.menubar
    root.geometry(porcupine.config['gui']['default_geometry'])
    root.title("Porcupine")
    root.protocol('WM_DELETE_WINDOW', editor.do_quit)
    root.mainloop()


if __name__ == '__main__':
    main()
