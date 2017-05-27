"""Run Porcupine."""

import argparse
import logging
import os
import platform
import sys
import tkinter as tk

import porcupine.editor
from porcupine import dirs, logs, pluginloader, tabs, utils
from porcupine.settings import config, color_themes
from porcupine.textwidget import init_font

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
        '-v', '--version', action='version',
        version=("Porcupine %s" % porcupine.__version__),
        help="display the Porcupine version number and exit")
    parser.add_argument(
        'file', metavar='FILES', nargs=argparse.ZERO_OR_MORE,
        help="open these files when the editor starts, - means stdin")
    parser.add_argument(
        '--verbose', action='store_true',
        help="print same debugging messages to stderr as to log file")
    parser.add_argument(
        '--shuffle-plugins', action='store_true',
        help=("respect setup_after, but otherwise setup the plugins "
              "in a random order instead of alphabetical order"))
    args = parser.parse_args()

    dirs.makedirs()
    logs.setup(verbose=args.verbose)
    log.info("starting Porcupine %s on %s", porcupine.__version__,
             platform.platform().replace('-', ' '))
    log.info("running on Python %d.%d.%d from %s",
             *(list(sys.version_info[:3]) + [sys.executable]))

    color_themes.load()
    config.load()

    root = tk.Tk()
    init_font()     # uses the root implicitly

    editor = porcupine.editor.Editor(root)
    editor.pack(fill='both', expand=True)

    root['menu'] = editor.menubar
    root.geometry(config['GUI', 'default_size'])
    root.title("Porcupine")
    root.protocol('WM_DELETE_WINDOW', editor.do_quit)

    # the root window has focus when there are no tabs, the bindings
    # must be copied after loading the plugins
    pluginloader.load(editor, args.shuffle_plugins)
    utils.copy_bindings(editor, root)

    for path in args.file:
        if path == '-':
            tab = tabs.FileTab.from_file_object(editor.tabmanager, sys.stdin)
            utils.copy_bindings(editor, tab.textwidget)
            editor.tabmanager.add_tab(tab)
            continue

        # the editor doesn't create new files when opening, so we
        # need to take care of that here
        path = os.path.abspath(path)
        if os.path.exists(path):
            tab = tabs.FileTab.from_path(editor.tabmanager, path)
        else:
            tab = tabs.FileTab.from_path(editor.tabmanager, path, content='')
        utils.copy_bindings(editor, tab.textwidget)
        editor.tabmanager.add_tab(tab)

    # the user can change the settings only if we get here, so
    # there's no need to try/finally the whole thing
    try:
        root.mainloop()
    finally:
        config.save()

    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
