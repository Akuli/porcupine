"""Run Porcupine."""

import argparse
import logging
import os
import platform
from queue import Empty         # queue is a handy variable name
import sys
import tkinter as tk

import porcupine
from porcupine import _ipc, _logs, _pluginloader, dirs, filetypes
from porcupine.settings import config

log = logging.getLogger(__name__)


def _iter_queue(queue):
    while True:
        try:
            yield queue.get(block=False)
        except Empty:
            break


def queue_opener(queue):
    gonna_focus = False
    for path, content in _iter_queue(queue):
        # if porcupine is running and the user runs it again without any
        # arguments, then path and content are None and we just focus
        # the editor window
        gonna_focus = True
        if (path, content) != (None, None):
            porcupine.open_file(path, content)

    window = porcupine.get_main_window()
    if gonna_focus:
        window.focus_set()      # FIXME
    window.after(200, queue_opener, queue)


def main():
    # sys.argv[0] is '__main__.py', so we can't use that as the prog
    # these hard-coded progs are wrong in some situations, but at least
    # better than '__main__.py'
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
        help="open these files when Porcupine starts, - means stdin")
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
        with f:
            if f == sys.stdin:
                filelist.append((None, f.read()))
            else:
                filelist.append((os.path.abspath(f.name), f.read()))

    try:
        if filelist:
            _ipc.send(filelist)
            print("The", ("file" if len(filelist) == 1 else "files"),
                  "will be opened in the already running Porcupine.")
        else:
            # see queue_opener()
            _ipc.send([(None, None)])
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

    filetypes.init()

    root = tk.Tk()
    porcupine.init(root)
    root.title("Porcupine")
    root.geometry(config['GUI', 'default_size'])
    root.protocol('WM_DELETE_WINDOW', porcupine.quit)

    _pluginloader.load(shuffle=args.shuffle_plugins)

    # see queue_opener()
    for path, content in filelist:
        if (path, content) != (None, None):
            porcupine.open_file(path, content)

    # the user can change the settings only if we get here, so there's
    # no need to wrap the try/with/finally/whatever the whole thing
    with _ipc.session() as queue:
        root.after_idle(queue_opener, queue)
        try:
            root.mainloop()
        finally:
            config.save()

    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
