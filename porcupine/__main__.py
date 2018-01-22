"""Parse arguments and run Porcupine using ``_run.py``."""

import argparse
import logging
import os
import sys

from porcupine import pluginloader, get_tab_manager, tabs, utils
import porcupine.plugins    # .plugins for porcupine.plugins.__path__

log = logging.getLogger(__name__)


# these actions are based on argparse's source code

class _PrintPlugindirAction(argparse.Action):

    def __init__(self, option_strings, dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest,
                         default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print("You can install plugins here:\n\n    %s\n"
              % porcupine.plugins.__path__[0])
        parser.exit()


# "porcupine -n a b c -n" works, but unfortunately "porcupine a -n b" doesn't
class _ExtendAction(argparse.Action):

    def __init__(self, option_strings, dest, nargs=None, const=None,
                 default=None, type=None, choices=None, required=False,
                 help=None, metavar=None):
        assert nargs != 0 and (const is None or nargs == argparse.OPTIONAL)
        super().__init__(option_strings=option_strings, dest=dest, nargs=nargs,
                         const=const, default=default, type=type,
                         choices=choices, required=required, help=help,
                         metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, [])
        getattr(namespace, self.dest).extend(values)


_EPILOG = r"""
Examples:
  %(prog)s                    # run Porcupine normally
  %(prog)s file1.py file2.js  # open the given files on startup
  %(prog)s -nnn               # create 3 new files
  %(prog)s --no-plugins       # understand the power of plugins
  %(prog)s --verbose          # produce lots of nerdy output
"""


def main():
    if os.path.basename(sys.argv[0]) == '__main__.py':
        prog = '%s -m porcupine' % utils.short_python_command
    else:
        prog = os.path.basename(sys.argv[0])    # argparse default
    parser = argparse.ArgumentParser(
        prog=prog, epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '-v', '--version', action='version',
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
        '-n', '--new-file', dest='files', action='append_const', const=None,
        help='create a "New File" tab, may be given multiple times')

    plugingroup = parser.add_argument_group("plugin loading options")
    plugingroup.add_argument(
        '--no-plugins', action='store_false', dest='yes_plugins',
        help=("don't load any plugins, this is useful for "
              "understanding how much can be done with plugins"))
    plugingroup.add_argument(
        '--without-plugin', metavar='PLUGIN', action='append', default=[],
        help=("don't load PLUGIN, e.g. --without-plugin=highlight "
              "runs Porcupine without syntax highlighting"))
    plugingroup.add_argument(
        '--shuffle-plugins', action='store_true',
        help=("respect setup_before and setup_after, but otherwise setup the "
              "plugins in a random order instead of sorting by name "
              "alphabetically"))

    parser.add_argument(
        '--verbose', action='store_true',
        help=("print all logging messages to stderr, only warnings and errors "
              "are printed by default"))

    args = parser.parse_args()

    filelist = []
    for file in args.files:
        if file is sys.stdin:
            # don't close stdin so it's possible to do this:
            #
            #   $ porcupine - -
            #   bla bla bla
            #   ^D
            #   bla bla
            #   ^D
            filelist.append((None, file.read()))
        elif file is None:
            # -n or --new-file was used
            filelist.append((None, ''))
        else:
            with file:
                filelist.append((os.path.abspath(file.name), file.read()))

    porcupine.init(verbose_logging=args.verbose)
    if args.yes_plugins:
        plugin_names = pluginloader.find_plugins()
        log.info("found %d plugins", len(plugin_names))
        for name in args.without_plugin:
            if name in plugin_names:
                plugin_names.remove(name)
            else:
                log.warning("no plugin named %r, cannot load without it", name)

        pluginloader.load(plugin_names, shuffle=args.shuffle_plugins)

    tabmanager = get_tab_manager()
    for path, content in filelist:
        tabmanager.add_tab(tabs.FileTab(tabmanager, content, path))

    porcupine.run()
    log.info("exiting Porcupine successfully")


if __name__ == '__main__':
    main()
