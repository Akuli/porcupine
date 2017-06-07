"""Run Porcupine."""

import argparse
import logging
import os
import platform
from queue import Empty         # queue is a handy variable name
import sys
import tkinter as tk
import traceback

import porcupine.editor
from porcupine import dirs, _ipc, _logs, _pluginloader, settings, tabs, utils

__all__ = ['main']

log = logging.getLogger(__name__)

# weird values so they don't conflict with anything
REGULAR_FILE = 0xF173
STDIN_CONTENTS = 0x57D10
FOCUS = 0xF0C05


def open_file(editor, path):
    # the editor doesn't create new files when opening, so we need to
    # take care of that here

    if isinstance(path, str):
        try:
            if os.path.exists(path):
                tab = tabs.FileTab.from_path(editor.tabmanager, path)
            else:
                tab = tabs.FileTab.from_path(editor.tabmanager, path,
                                             content='')
        except (OSError, UnicodeError):
            utils.errordialog("Opening failed", "Cannot open '%s'!" % path,
                              traceback.format_exc())
            return
    else:
        tab = open_content(editor, path.read())
        tab.path = path.name

    if tab is not None:
        utils.copy_bindings(editor, tab.textwidget)
        editor.tabmanager.add_tab(tab)


def open_content(editor, content):
    """
    Open a tab with the specified content.
    """
    tab = tabs.FileTab(editor.tabmanager)

    tab.textwidget.insert('1.0', content)
    tab.textwidget.edit_reset()   # reset undo/redo
    tab.mark_saved()

    utils.copy_bindings(editor, tab.textwidget)
    editor.tabmanager.add_tab(tab)

    return tab


def queue_opener(editor, queue):
    try:
        kind, value = queue.get(block=False)
    except Empty:
        # We still want to pass, not return, here because we need to schedule
        # the next call.
        pass
    else:
        # We utilize the no-exception else so that in any case there's a file
        # or whatever the Porcupine window is focused. This allows sending
        # FOCUS without actually opening any file.
        utils.get_root().focus_set()
        while True:
            if kind == FOCUS:
                pass
            elif kind == REGULAR_FILE:
                open_file(editor, value)
            elif kind == STDIN_CONTENTS:
                open_content(editor, value)
            else:
                raise ValueError("Unknown type {!r}".format(kind))

            # We purposefully only get the next one at the end so we can do the
            # trick where we focus if there's anything in the queue.
            try:
                kind, value = queue.get(block=False)
            except Empty:
                break

    editor.after(200, queue_opener, editor, queue)


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
        '-v', '--version', action='version',
        version=("Porcupine %s" % porcupine.__version__),
        help="display the Porcupine version number and exit")
    parser.add_argument(
        'file', metavar='FILES', nargs=argparse.ZERO_OR_MORE,
        type=argparse.FileType("r"),
        help="open these files when the editor starts, - means stdin")
    parser.add_argument(
        '--verbose', action='store_true',
        help="print same debugging messages to stderr as to log file")
    parser.add_argument(
        '--shuffle-plugins', action='store_true',
        help=("respect setup_after, but otherwise setup the plugins "
              "in a random order instead of alphabetical order"))
    args = parser.parse_args()

    filelist = []

    for f in args.file:
        if f == sys.stdin:
            filelist.append((STDIN_CONTENTS, f.read()))
        else:
            filelist.append((REGULAR_FILE, f))

    try:
        if filelist:
            _ipc.send(filelist)
            print("The", ("file" if len(filelist) == 1 else "files"),
                  "will be opened in the already running Porcupine.")
        else:
            # see comments in queue_opener()
            _ipc.send([(FOCUS, None)])
            print("Porcupine is already running.")
        return
    except ConnectionRefusedError:
        # not running yet, become the Porcupine that other Porcupines
        # connect to
        pass

    dirs.makedirs()
    _logs.setup(verbose=args.verbose)
    log.info("starting Porcupine %s on %s", porcupine.__version__,
             platform.platform().replace('-', ' '))
    log.info("running on Python %d.%d.%d from %s",
             *(list(sys.version_info[:3]) + [sys.executable]))

    root = tk.Tk()
    settings.load()

    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    root['menu'] = editor.menubar
    root.geometry(settings.config['GUI', 'default_size'])
    root.title("Porcupine")
    root.protocol('WM_DELETE_WINDOW', editor.do_quit)

    # the root window has focus when there are no tabs, the bindings
    # must be copied after loading the plugins
    _pluginloader.load(editor, args.shuffle_plugins)
    utils.copy_bindings(editor, root)

    for kind, value in filelist:
        if kind == REGULAR_FILE:
            open_file(editor, value)
        elif kind == STDIN_CONTENTS:
            open_content(editor, value)

    # the user can change the settings only if we get here, so there's
    # no need to wrap the try/with/finally/whatever the whole thing
    with _ipc.session() as queue:
        root.after_idle(queue_opener, editor, queue)
        try:
            root.mainloop()
        finally:
            settings.save()

    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
