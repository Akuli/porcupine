"""Run the editor."""

import argparse
import logging
import os
import platform
import sys
import tkinter as tk

import porcupine.editor
from porcupine import settings


def main():
    # sys.argv[0] is '__main__.py', so we can't use that as the prog.
    # these hard-coded progs are wrong in some situations, but at least
    # better than '__main__.py'.
    if platform.system() == 'Windows':
        prog = 'py -m porcupine'
    else:
        prog = '%s -m porcupine' % os.path.basename(sys.executable)

    parser = argparse.ArgumentParser(prog=prog, description=porcupine.__doc__)
    parser.add_argument(
        'file', metavar='FILES', nargs=argparse.ZERO_OR_MORE,
        help="open these files when the editor starts, - means stdin")
    parser.add_argument(
        '--verbose', '-v', dest='loglevel', action='store_const',
        const=logging.DEBUG, default=logging.WARNING,
        help="print more debugging messages to stderr")
    args = parser.parse_args()

    logging.basicConfig(
        format='%(name)s: %(message)s',
        level=args.loglevel,
    )

    root = tk.Tk()
    settings.load()     # root must exist first

    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    for file in args.file:
        if file == '-':
            # read stdin
            content = sys.stdin.read()
            tab = editor.new_file()
            tab.textwidget.insert('1.0', content)
            tab.textwidget.edit_reset()   # reset undo/redo
            tab.mark_saved()
            continue

        # the editor doesn't create new files when opening, so we need to
        # take care of that here
        file = os.path.abspath(file)
        if os.path.exists(file):
            editor.open_file(file)
        else:
            editor.open_file(file, content='')

    root['menu'] = editor.menubar
    root.geometry(settings.config['gui:default_geometry'])
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
