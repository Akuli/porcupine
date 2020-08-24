"""Everything related to filetypes.toml."""

import argparse
import fnmatch
from functools import partial
import logging
import pathlib
import re
import tkinter.ttk
from typing import Any, Dict, List, Optional, Tuple, Union

import pygments.lexer   # type: ignore
import pygments.lexers  # type: ignore
import pygments.token   # type: ignore
from pygments.util import ClassNotFound     # type: ignore
import toml

from porcupine import get_main_window, get_parsed_args, get_tab_manager
from porcupine import dirs, filedialog_kwargs, menubar, settings, tabs, utils


log = logging.getLogger(__name__)
FileType = Dict[str, Any]
filetypes: Dict[str, FileType] = {}
USER_FILETYPES_PATH = dirs.configdir / 'filetypes.toml'


def is_list_of_strings(obj: object) -> bool:
    return isinstance(obj, list) and all(isinstance(item, str) for item in obj)


def load_filetypes() -> None:
    defaults_path = pathlib.Path(__file__).absolute().parent.parent / 'default_filetypes.toml'

    filetypes.update(toml.load(defaults_path))

    user_filetypes: Dict[str, FileType] = {}
    try:
        user_filetypes = dict(toml.load(USER_FILETYPES_PATH))
    except FileNotFoundError:
        log.info(f"'{USER_FILETYPES_PATH}' not found, creating")
        with USER_FILETYPES_PATH.open('x') as file:   # error if exists
            file.write('''\
# Putting filetype configuration into this file overrides Porcupine's default
# filetype configuration. You can read the default configuration here:
#
#    https://github.com/Akuli/porcupine/blob/master/porcupine/default_filetypes.toml
''')
    except (OSError, UnicodeError, toml.TomlDecodeError):
        log.exception(f"reading '{USER_FILETYPES_PATH}' failed, using defaults")

    # toml.load can take multiple file names, but it doesn't merge the configs
    for name, updates in user_filetypes.items():
        filetypes.setdefault(name, {}).update(updates)

    for name, filetype in filetypes.items():
        # everything except filename_patterns and shebang_regex is handled by Settings objects
        if ('filename_patterns' in filetype and
                not is_list_of_strings(filetype['filename_patterns'])):
            log.error(f"filename_patterns is not a list of strings in [{name}] section")
            del filetype['filename_patterns']

        if 'shebang_regex' in filetype:
            try:
                re.compile(filetype['shebang_regex'])
            except re.error:
                log.error(f"invalid shebang_regex in [{name}] section")
                del filetype['shebang_regex']

        filetype.setdefault('filename_patterns', [])
        filetype.setdefault('shebang_regex', r'this regex matches nothing^')

        # if no langserver configured, then don't leave langserver from
        # previous filetype around when switching filetype
        filetype.setdefault('langserver', None)


def get_filetype_from_matches(
    matches: Dict[str, FileType],
    they_match_what: str,
) -> Optional[FileType]:
    if not matches:
        return None

    [result, *rest] = matches.values()
    if rest:
        names = ', '.join(matches.keys())
        log.warning(f"multiple file types match {they_match_what}: {names}")
    return result


def guess_filetype_from_path(filepath: pathlib.Path) -> Optional[FileType]:
    return get_filetype_from_matches({
        name: filetype
        for name, filetype in filetypes.items()
        if any(
            fnmatch.fnmatch(filepath.name, pat)
            for pat in filetype['filename_patterns']
        )
    }, f"filename {filepath.name!r}")


def guess_filetype_from_shebang(content_start: str) -> Optional[FileType]:
    shebang_line = content_start.split('\n')[0]
    matches: Dict[str, FileType] = {}

    for name, filetype in filetypes.items():
        if re.search(filetype['shebang_regex'], shebang_line) is not None:
            matches[name] = filetype

    return get_filetype_from_matches(matches, f"shebang {shebang_line!r}")


# TODO: take content as argument
def guess_filetype(filepath: pathlib.Path) -> FileType:
    filetype = guess_filetype_from_path(filepath)
    if filetype is not None:
        return filetype

    try:
        # the shebang is read as utf-8 because the filetype config file
        # is utf-8
        with filepath.open('r', encoding='utf-8') as file:
            # don't read the entire file if it's huge
            shebang_line: Optional[str] = file.readline(1000)
    except (UnicodeError, OSError):
        shebang_line = None

    if shebang_line is not None:
        filetype = guess_filetype_from_shebang(shebang_line)
        if filetype is not None:
            return filetype

    # if nothing else works, create a new filetype automagically based on pygments
    try:
        lexer = pygments.lexers.get_lexer_for_filename(filepath)
    except ClassNotFound:
        if shebang_line is None:
            return filetypes['Plain Text']  # give up
        lexer = pygments.lexers.guess_lexer(shebang_line)
        if isinstance(lexer, pygments.lexers.TextLexer):
            return filetypes['Plain Text']  # give up

    return {
        'pygments_lexer': type(lexer).__module__ + '.' + type(lexer).__name__,
        'langserver': None,
    }


def get_filetype_for_tab(tab: tabs.FileTab) -> FileType:
    if tab.path is None:
        return filetypes[settings.get('default_filetype', str)]
    # FIXME: this may read the shebang from the file, but the file
    #        might not be saved yet because save_as() sets self.path
    #        before saving, and that's when this runs
    return guess_filetype(tab.path)


def apply_filetype_to_tab(tab: tabs.FileTab, filetype: FileType) -> None:
    log.info(f"applying filetype settings: {filetype!r}")
    for name, value in filetype.items():
        # Ignore stuff used only for guessing the correct filetype
        if name not in {'filename_patterns', 'shebang_regex'}:
            tab.settings.set(name, value, from_config=True)


def setup_settings_stuff() -> None:
    settings.add_option('default_filetype', 'Python')
    settings.add_combobox(
        settings.get_section('General'), 'default_filetype', "Default filetype for new files:",
        values=sorted(filetypes.keys(), key=str.casefold),
    )
    settings.add_config_file_button(settings.get_section('Config Files'), USER_FILETYPES_PATH)


def configure_filetypes_kwargs() -> None:
    filetypes_for_filedialog: List[Tuple[
        str,
        Union[str, Tuple[str, ...]],  # tkinter works this way
    ]] = [("All Files", "*")]
    for name, filetype in filetypes.items():
        if name == "Plain Text":
            # can just use "All Files" for this
            continue

        patterns = tuple(
            # "*.py" doesn't work on windows, but ".py" works and does the same thing
            # See "SPECIFYING EXTENSIONS" in tk_getOpenFile manual page
            pattern.lstrip('*')
            for pattern in filetype['filename_patterns']
        )
        filetypes_for_filedialog.append((name, patterns))

    filedialog_kwargs['filetypes'] = filetypes_for_filedialog


def on_path_changed(tab: tabs.FileTab, junk: object = None) -> None:
    log.info(f"file path changed: {tab.path}")
    apply_filetype_to_tab(tab, get_filetype_for_tab(tab))


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        on_path_changed(tab)
        tab.bind('<<PathChanged>>', partial(on_path_changed, tab), add=True)


def setup_argument_parser(parser: argparse.ArgumentParser) -> None:
    def parse_filetype_name(name: str) -> FileType:
        try:
            return filetypes[name]
        except KeyError:
            raise argparse.ArgumentTypeError(f"no filetype named {name!r}")

    load_filetypes()
    parser.add_argument(
        '-n', '--new-file', metavar='FILETYPE', action='append', type=parse_filetype_name,
        help='create a "New File" tab with a filetype from filetypes.toml')
    # TODO: make sure to get error for bad filetypes


def open_files_specified_on_command_line(junk: object) -> None:
    for filetype in (get_parsed_args().new_file or []):   # new_file may be None
        tab = tabs.FileTab(get_tab_manager())
        get_tab_manager().add_tab(tab)  # sets default filetype
        apply_filetype_to_tab(tab, filetype)  # sets correct filetype


def menu_callback(filetype: FileType) -> None:
    tab = get_tab_manager().select()
    assert isinstance(tab, tabs.FileTab)
    apply_filetype_to_tab(tab, filetype)


def create_filetypes_menu() -> None:
    for name, filetype in filetypes.items():
        safe_name = name.replace('/', '\\')   # TODO: unicode slash character
        menubar.get_menu("Filetypes").add_command(
            label=safe_name,
            command=partial(menu_callback, filetype))
        menubar.set_enabled_based_on_tab(f"Filetypes/{safe_name}", (lambda tab: isinstance(tab, tabs.FileTab)))


def setup() -> None:
    # load_filetypes() got already called in setup_argument_parser()
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
    get_main_window().bind('<<PluginsLoaded>>', open_files_specified_on_command_line, add=True)
    setup_settings_stuff()
    configure_filetypes_kwargs()
    create_filetypes_menu()
