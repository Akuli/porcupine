"""Run the editor."""

import argparse
import os
import tkinter as tk

import porcupine.editor
from porcupine import settings


def main():
    parser = argparse.ArgumentParser(description=porcupine.__doc__)
    parser.add_argument(
        'file', nargs=argparse.ZERO_OR_MORE,
        help="open this file when the editor starts")
    args = parser.parse_args()

    settings.load()

    root = tk.Tk()
    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    for file in args.file:
        file = os.path.abspath(file)

        # the editor doesn't create new files when opening, so we need to
        # take care of that here
        if os.path.exists(file):
            editor.open_file(file)
        else:
            editor.open_file(file, content='')

    root['menu'] = editor.menubar
    root.geometry(settings.config['gui']['default_geometry'])
    root.title("Porcupine")
    root.protocol('WM_DELETE_WINDOW', editor.do_quit)

    # the user can change the settings only if we get here, so there's
    # no need to try/finally the whole thing
    try:
        root.mainloop()
    finally:
        settings.save()


if __name__ == '__main__':
    main()
