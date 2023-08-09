from __future__ import annotations

import argparse
import logging

from porcupine import __version__ as porcupine_version
from porcupine import _logs, _state, dirs, get_main_window, menubar, pluginloader, settings

log = logging.getLogger(__name__)


_EPILOG = r"""
Examples:
  %(prog)s                    # run Porcupine normally
  %(prog)s file1.py file2.js  # open the given files on startup
  %(prog)s -n Python          # create a new Python file
  %(prog)s --no-plugins       # understand the power of plugins
  %(prog)s -v                 # produce lots of output for debugging
"""


def main() -> None:
    # Arguments are parsed in two steps:
    #   1. only the arguments needed for importing plugins
    #   2. everything else
    #
    # Between those steps, plugins get a chance to add more command-line options.
    parser = argparse.ArgumentParser(
        prog="porcupine",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,  # help in step 1 wouldn't show options added by plugins
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Porcupine {porcupine_version}",
        help="display the Porcupine version number and exit",
    )

    verbose_group = parser.add_mutually_exclusive_group()
    verbose_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help=(
            "print all logging messages to stderr, only warnings and errors "
            "are printed by default (but all messages always go to a log "
            "file as well)"
        ),
    )
    verbose_group.add_argument(
        "--verbose-logger",
        action="append",  # Allow passing multiple times: --verbose-logger foo --verbose-logger bar
        help=(
            "increase verbosity for just one logger only, e.g. "
            "--verbose-logger=porcupine.plugins.highlight "
            "to see messages from highlight plugin"
        ),
    )

    plugingroup = parser.add_argument_group("plugin loading options")
    plugingroup.add_argument(
        "--no-plugins",
        action="store_false",
        dest="use_plugins",
        help=(
            "don't load any plugins, this is useful for "
            "understanding how much can be done with plugins"
        ),
    )
    plugingroup.add_argument(
        "--without-plugins",
        metavar="PLUGINS",
        default="",
        help=(
            "don't load PLUGINS, e.g. --without-plugins=highlight disables syntax highlighting,"
            " multiple plugin names can be given comma-separated"
        ),
    )

    args_parsed_in_first_step, junk = parser.parse_known_args()

    dirs.user_cache_path.mkdir(parents=True, exist_ok=True)
    (dirs.user_config_path / "plugins").mkdir(parents=True, exist_ok=True)
    dirs.user_log_path.mkdir(parents=True, exist_ok=True)
    _logs.setup(
        all_loggers_verbose=args_parsed_in_first_step.verbose,
        verbose_loggers=(args_parsed_in_first_step.verbose_logger or []),
    )

    settings.init_enough_for_using_disabled_plugins_list()
    if args_parsed_in_first_step.use_plugins:
        if args_parsed_in_first_step.without_plugins:
            disable_list = args_parsed_in_first_step.without_plugins.split(",")
        else:
            disable_list = []
        pluginloader.import_plugins(disable_list)

        bad_disables = set(disable_list) - {info.name for info in pluginloader.plugin_infos}
        if bad_disables:
            one_of_them, *the_rest = bad_disables
            parser.error(f"--without-plugins: no plugin named {one_of_them!r}")

    parser.add_argument("--help", action="help", help="show this message")
    pluginloader.run_setup_argument_parser_functions(parser)
    parser.add_argument(
        "files",
        metavar="FILES",
        nargs=argparse.ZERO_OR_MORE,
        help="open these files when Porcupine starts, - means stdin",
    )
    plugingroup.add_argument(
        "--shuffle-plugins",
        action="store_true",
        help=(
            "respect setup_before and setup_after, but otherwise setup the "
            "plugins in a random order instead of sorting by name "
            "alphabetically, useful for making sure that your plugin's "
            "setup_before and setup_after define everything needed; usually "
            "plugins are not shuffled in order to make the UI consistent"
        ),
    )

    args = parser.parse_args()
    _state.init(args)

    # Prevent showing up a not-ready-yet root window to user
    get_main_window().withdraw()

    settings.init_the_rest_after_initing_enough_for_using_disabled_plugins_list()
    menubar._init()
    pluginloader.run_setup_functions(args.shuffle_plugins)

    _state.open_files(args.files)

    get_main_window().deiconify()
    try:
        get_main_window().mainloop()
    finally:
        settings.save()
    log.info("exiting Porcupine successfully")


# python3 -m pocupine
if __name__ == "__main__":
    main()
