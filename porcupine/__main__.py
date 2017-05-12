"""Run Porcupine."""

import argparse
import logging
import os
import platform
import sys
import tkinter as tk

import porcupine.editor
from porcupine import dirs, logs, plugins, settings

log = logging.getLogger(__name__)


def main():
    # sys.argv[0] is '__main__.py', so we can't use that as the prog.
    # these hard-coded progs are wrong in some situations, but at least
    # better than '__main__.py'.
    if platform.system() == 'Windows':
        prog = 'py -m porcupine'
    else:
        prog = '%s -m porcupine' % os.path.basename(sys.executable)

    parser = argparse.ArgumentParser(
        prog=prog, description=porcupine.__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'file', metavar='FILES', nargs=argparse.ZERO_OR_MORE,
        help="open these files when the editor starts, - means stdin")
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help="print same debugging messages to stderr as to log file")
    args = parser.parse_args()

    dirs.makedirs()
    logs.setup(verbose=args.verbose)
    log.info("starting Porcupine on %s", platform.platform().replace('-', ' '))
    log.info("running on Python %d.%d.%d from %s",
             *(list(sys.version_info[:3]) + [sys.executable]))

    root = tk.Tk()
    settings.load()     # root must exist first

    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    root['menu'] = editor.menubar
    root.geometry(settings.config['GUI']['default_size'])
    root.title("Porcupine")
    root.protocol('WM_DELETE_WINDOW', editor.do_quit)

    plugins.load(editor)

    for file in args.file:
        if file == '-':
            # read stdin
            tab = editor.new_file()
            for line in sys.stdin:
                tab.textwidget.insert('end-1c', line)
            tab.textwidget.edit_reset()   # reset undo/redo
            tab.mark_saved()
            continue

        # the editor doesn't create new files when opening, so we
        # need to take care of that here
        file = os.path.abspath(file)
        if os.path.exists(file):
            editor.open_file(file)
        else:
            editor.open_file(file, content='')

    # the user can change the settings only if we get here, so
    # there's no need to try/finally the whole thing
    try:
        root.mainloop()
    finally:
        settings.save()

    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
