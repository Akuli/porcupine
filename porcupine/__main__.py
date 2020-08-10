"""Parse arguments and run Porcupine using ``_run.py``."""

import argparse
import logging
import pathlib
import sys
from typing import Any, Dict, List, Optional, Tuple

from porcupine import _logs, filetypes, get_tab_manager, pluginloader, tabs
import porcupine.plugins    # .plugins for porcupine.plugins.__path__

log = logging.getLogger(__name__)


# these actions are based on argparse's source code

class _PrintPlugindirAction(argparse.Action):

    def __init__(   # type: ignore
            self, option_strings, dest=argparse.SUPPRESS,
            default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest,
                         default=default, nargs=0, help=help)

    def __call__(   # type: ignore
            self, parser, namespace, values, option_string=None):
        print("You can install plugins here:\n\n    %s\n"
              % porcupine.plugins.__path__[0])
        parser.exit()


class _ExtendAction(argparse.Action):

    def __init__(   # type: ignore
            self, option_strings, dest, nargs=None, const=None,
            default=None, type=None, choices=None, required=False,
            help=None, metavar=None):
        assert nargs != 0 and (const is None or nargs == argparse.OPTIONAL)
        super().__init__(option_strings=option_strings, dest=dest, nargs=nargs,
                         const=const, default=default, type=type,
                         choices=choices, required=required, help=help,
                         metavar=metavar)

    def __call__(   # type: ignore
            self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).extend(values)


_EPILOG = r"""
Examples:
  %(prog)s                    # run Porcupine normally
  %(prog)s file1.py file2.js  # open the given files on startup
  %(prog)s -n Python          # create a new Python file
  %(prog)s --no-plugins       # understand the power of plugins
  %(prog)s -v                 # produce lots of output for debugging
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        epilog=_EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--version', action='version',
        version=("Porcupine %s" % porcupine.__version__),
        help="display the Porcupine version number and exit")
    parser.add_argument(
        '--print-plugindir', action=_PrintPlugindirAction,
        help="find out where to install custom plugins")
    parser.add_argument(
        'files', metavar='FILES', action=_ExtendAction,
        # FIXME: this uses the system-default encoding :/
        nargs=argparse.ZERO_OR_MORE, type=argparse.FileType("r"),
        help="open these files when Porcupine starts, - means stdin")
    parser.add_argument(
        '-n', '--new-file', metavar='FILETYPE', action='append',
        help='create a "New File" tab with a filetype from filetypes.toml')

    plugingroup = parser.add_argument_group("plugin loading options")
    plugingroup.add_argument(
        '--no-plugins', action='store_false', dest='yes_plugins',
        help=("don't load any plugins, this is useful for "
              "understanding how much can be done with plugins"))
    plugingroup.add_argument(
        '--without-plugins', metavar='PLUGINS', default='',
        help=("don't load PLUGINS (see --print-plugindir), "
              "e.g. --without-plugins=highlight disables syntax highlighting, "
              "multiple plugin names can be given comma-separated"))
    plugingroup.add_argument(
        '--shuffle-plugins', action='store_true',
        help=("respect setup_before and setup_after, but otherwise setup the "
              "plugins in a random order instead of sorting by name "
              "alphabetically, useful for making sure that your plugin's "
              "setup_before and setup_after define everything needed; usually "
              "plugins are not shuffled in order to make the UI consistent"))

    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help=("print all logging messages to stderr, only warnings and errors "
              "are printed by default (but all messages always go to a log "
              "file in %s as well)" % _logs.LOG_DIR))

    args = parser.parse_args()

    # Make sure to get error before doing any gui stuff if reading file fails
    # or specified filetype doesn't exist.
    filelist: List[Tuple[Optional[pathlib.Path], str, Optional[Dict[str, Any]]]] = []

    for file in args.files:
        if file is sys.stdin:
            # don't close stdin so it's possible to do this:
            #
            #   $ porcupine - -
            #   bla bla bla
            #   ^D
            #   bla bla
            #   ^D
            filelist.append((None, file.read(), None))
        else:
            with file:
                filelist.append(
                    (pathlib.Path(file.name).absolute(), file.read(), None))

    filetypes._init()
    for filetype_name in (args.new_file or []):   # args.new_file may be None
        filetype = None   # fixes mypy error
        try:
            filetype = filetypes.get_filetype_by_name(filetype_name)
        except KeyError:
            parser.error(f"no filetype named {filetype_name!r}")
        filelist.append((None, '', filetype))

    porcupine.init(verbose_logging=args.verbose)
    if args.yes_plugins:
        plugin_names = pluginloader.find_plugins()
        log.info("found %d plugins", len(plugin_names))

        if args.without_plugins:
            for name in args.without_plugins.split(','):
                if name in plugin_names:
                    plugin_names.remove(name)
                else:
                    log.warning(
                        "no plugin named %r, cannot load without it", name)

        pluginloader.load(plugin_names, shuffle=args.shuffle_plugins)

    tabmanager = get_tab_manager()
    for path, content, filetype in filelist:
        tab = tabs.FileTab(tabmanager, content, path)
        if filetype is not None:
            tab.filetype_to_settings(filetype)
        tabmanager.add_tab(tab)

    porcupine.run()
    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
