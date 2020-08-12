# I found this library but it sucks lol, doesn't even support *.{py,js}:
#
#    https://pypi.org/project/EditorConfig/
#
# Many comments in this file are quotes from https://editorconfig.org/
import configparser
import dataclasses
import logging
import pathlib
import re
from typing import Dict, List, Optional, Tuple, Union

from porcupine import get_tab_manager, tabs, utils

log = logging.getLogger(__name__)


# "root: special property that should be specified at the top of the file
# outside of any sections."
_STUFF_WITH_NO_SECTION = "stuff in this section is at the beginning of the file"

# configparser has a stupid special [DEFAULT] section that can't be disabled,
# but it can be renamed
_DEFAULT_SECTION_NAME = "this section is not used for anything but can't be disabled"


@dataclasses.dataclass
class Section:
    glob_relative_to: pathlib.Path
    path_glob: str
    config: Dict[str, str]


# Sections later in resulting list override earlier sections: "EditorConfig
# files are read top to bottom and the most recent rules found take precedence."
def parse_file(path: pathlib.Path) -> Tuple[List[Section], bool]:
    log.debug(f"parsing {path}")

    # "EditorConfig files should be UTF-8 encoded, with either CRLF or LF line
    # separators."
    #
    # Python accepts CRLF and LF by default
    with path.open('r', encoding='utf-8') as file:
        content = '[' + _STUFF_WITH_NO_SECTION + ']\n' + file.read()

    # "EditorConfig files use an INI format that is compatible with the format used
    # by Python ConfigParser Library, but ..."
    parser = configparser.ConfigParser(
        interpolation=None,
        default_section=_DEFAULT_SECTION_NAME,
        # configparser defaults agree about these:
        #   - "... and octothorpes (#) or semicolons (;) are used for comments."
        #   - "Comments should go on their own lines."
        comment_prefixes=(';', '#'),
        inline_comment_prefixes=(';', '#'),
        # whitespace should be ignored, but configparser uses it to do
        # multiline values by default
        empty_lines_in_values=False,
    )

    # "... [ and ] are allowed in the section names."
    # TODO: create typeshed issue
    parser.SECTCRE = re.compile(r"\[(?P<header>.*)\]")  # type: ignore[attr-defined]

    try:
        parser.read_string(content, source=str(path))
    except configparser.Error:
        log.exception(f"error while parsing {path}")
        # it may be partially parsed, let's continue as if no error happened

    # "EditorConfig files are read top to bottom and the most recent rules
    # found take precedence."
    result = [
        Section(
            glob_relative_to=path.parent,
            # "The section names are filepath globs"
            path_glob=name,
            config={
                # "Currently all properties and values are case-insensitive.
                # They are lowercased when parsed."
                #
                # configparser lowercases keys by default
                key: value.lower()
                for key, value in section.items()
            }
        )
        for name, section in parser.items()
        if name not in {_STUFF_WITH_NO_SECTION, _DEFAULT_SECTION_NAME}
    ]

    root_string = parser[_STUFF_WITH_NO_SECTION].get('root', 'false')
    try:
        is_root = {'true': True, 'false': False}[root_string.lower()]
    except KeyError:
        log.error(
            "'root' should be set to 'true' or 'false' (case insensitive), "
            f"but it was set to {root_string!r}")
        is_root = False
    return (result, is_root)


def glob_match(glob: str, string: str) -> bool:
    ranges: List[range] = []
    regex = ''

    while glob:
        if glob.startswith((r'\*', r'\?', r'\[', r'\]', r'\{', r'\}')):
            # "Special characters can be escaped with a backslash so they won't
            # be interpreted as wildcard patterns."
            regex += re.escape(glob[1])
            glob = glob[2:]
        elif glob.startswith('**'):
            # "Matches any string of characters"
            regex += r'.*'
            glob = glob[2:]
        elif glob.startswith('*'):
            # "Matches any string of characters, except path separators (/)"
            regex += r'[^/]*'
            glob = glob[1:]
        elif glob.startswith('?'):
            # "Matches any single character"
            regex += r'.'
            glob = glob[1:]
        elif glob.startswith('['):
            # [name]	   Matches any single character in name
            # [!name]	  Matches any single character not in name
            end = glob.index(']')
            if glob.startswith('[!'):
                regex += r'[^' + re.escape(glob[2:end]) + r']'
            else:
                regex += r'[' + re.escape(glob[1:end]) + r']'
            glob = glob[(end + 1):]    # +1 to skip ']'
        elif glob.startswith('{'):
            # {num1..num2}	 Matches any integer numbers between num1 and num2,
            #               where num1 and num2 can be either positive or
            #               negative
            # {s1,s2,s3} 	  Matches any of the strings given (separated by commas)
            #
            # Here we assume that "positive or negative" was intended to also
            # include zero, even though 0 is not actually positive or negative.
            match = re.match(r'\{(-?[0-9]+)\.\.(-?[0-9]+)\}', glob)
            if match is None:
                # {s1,s2,s3}
                end = glob.index('}')
                strings = glob[1:end].split(',')
                regex += r'(?:' + r'|'.join(map(re.escape, strings)) + r')'
                glob = glob[(end + 1):]   # +1 to skip '}'
            else:
                # {num1..num2}
                #
                # I didn't feel like trying to create a regex to match any
                # integer between two given integers
                #
                # Also, specifying a huge range doesn't make the computer run
                # out of memory. This never creates a list of all allowed
                # values because of how range works in Python 3.
                min_value = int(match.group(1))
                max_value = int(match.group(2))
                ranges.append(range(min_value, max_value + 1))
                regex += r'(-?[0-9]+)'
                glob = glob[match.end():]
        else:
            # The character doesn't have a special meaning in globs, but it
            # might still have some special meaning in regexes (e.g. dot)
            regex += re.escape(glob[0])
            glob = glob[1:]

    match = re.fullmatch(regex, string)
    if match is None:
        return False

    integers = list(map(int, match.groups()))
    assert len(integers) == len(ranges)
    return all(integer in ranke for integer, ranke in zip(integers, ranges))


def get_config(path: pathlib.Path) -> Dict[str, str]:
    assert path.is_absolute()

    # last items in this list is considered the most important
    # i.e. every item overrides ones before it
    all_sections: List[Section] = []

    # "When opening a file, EditorConfig plugins look for a file named
    # .editorconfig in the directory of the opened file and in every parent
    # directory. A search for .editorconfig files will stop if the root
    # filepath is reached or ..."
    for parent in path.parents:
        if not (parent / '.editorconfig').is_file():
            continue
        sections, is_root = parse_file(parent / '.editorconfig')

        # "Properties from matching EditorConfig sections are applied in the order
        # they were read, so properties in closer files take precedence."
        #
        # I think those sentences contradict each other. To me it seems that
        # "closer" means the file with a longer path, so that the file taking
        # the most precedence is the one in the same directory with the source
        # file. That gets parsed first, so anything after that should go to the
        # beginning of all_sections.
        all_sections[0:0] = sections

        # "A search for .editorconfig files will stop if ... or an EditorConfig
        # file with root=true is found."
        if is_root:
            break

    result: Dict[str, str] = {}
    for section in all_sections:
        # "Only forward slashes (/, not backslashes) are used as path separators"
        relative = '/' + path.relative_to(section.glob_relative_to).as_posix()

        # editorconfig-core-c does this, doesn't seem to be documented anywhere
        # https://github.com/editorconfig/editorconfig-core-c/blob/e70d90d045e339374abda3fa664904fbba7f8d67/src/lib/editorconfig.c#L260-L266
        if section.path_glob.startswith('/'):
            glob = section.path_glob
        elif '/' in section.path_glob:
            glob = '/' + section.path_glob
        else:
            glob = '**/' + section.path_glob

        try:
            if not glob_match(glob, relative):
                continue
        except Exception:
            log.exception(f"error while globbing {section.path_glob}")
            continue

        for name, value in section.config.items():
            if value == 'unset':
                try:
                    del result[name]
                except KeyError:
                    pass
            else:
                result[name] = value
    return result


# https://github.com/editorconfig/editorconfig/wiki/EditorConfig-Properties

def get_tabs2spaces(config: Dict[str, str]) -> Optional[bool]:
    try:
        string = config['indent_style']
    except KeyError:
        return None

    if string == 'tab':
        return False
    if string == 'space':
        return True
    log.error(f"bad indent_style {string!r}")
    return None


def get_indent_size(config: Dict[str, str]) -> Optional[int]:
    try:
        string_value = config['indent_size']
        # "When set to tab, the value of tab_width (if specified) will be used."
        if string_value == 'tab':
            raise KeyError
    except KeyError:
        try:
            string_value = config['tab_width']
        except KeyError:
            return None

    try:
        return int(string_value)
    except ValueError:
        log.error(f"bad indent_size or tab_width {string_value!r}")
        return None


def get_encoding(config: Dict[str, str]) -> Optional[str]:
    try:
        encoding = config['charset']
    except KeyError:
        return None

    # "set to latin1, utf-8, utf-8-bom, utf-16be or utf-16le to control the
    # character set"
    #
    # i.e. only these are supported, and we must ignore anything else that
    # Python supports too.
    if encoding not in {'latin1', 'utf-8', 'utf-8-bom', 'utf-16be', 'utf-16le'}:
        log.error(f"bad charset {encoding!r}")
        return None
    return encoding


def get_max_line_length(config: Dict[str, str]) -> Optional[int]:
    try:
        string = config['max_line_length']
    except KeyError:
        return None

    try:
        return int(string)
    except ValueError:
        log.error(f"bad max_line_length {string!r}")
        return None


# TODO: end_of_line, trim_trailing_whitespace, insert_final_newline


def apply_config(config: Dict[str, str], tab: tabs.FileTab) -> None:
    updates: Dict[str, Union[str, int, None]] = {
        'tabs2spaces': get_tabs2spaces(config),
        'indent_size': get_indent_size(config),
        'encoding': get_encoding(config),
        'max_line_length': get_max_line_length(config),
    }
    for name, value in updates.items():
        if value is None:
            log.debug(f"{name} not specified in editorconfigs")
        else:
            log.info(f"setting {name} to {value}")
            if name == 'max_line_length':
                # this must work even if running without longlinemarker plugin
                # (or if longlinemarker's setup() runs after this plugin)
                tab.settings.set(name, value, from_config=True)
            else:
                tab.settings.set(name, value)


def get_config_and_apply_to_tab(tab: tabs.FileTab):
    assert tab.path is not None
    log.debug(f"applying settings to {tab.path}")
    apply_config(get_config(tab.path), tab)


def before_file_opens(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    assert isinstance(tab, tabs.FileTab)
    log.info(f"file opened: {tab.path}")
    get_config_and_apply_to_tab(tab)


def on_path_changed(event: utils.EventWithData) -> None:
    assert isinstance(event.widget, tabs.FileTab)
    if event.widget.path is not None:
        log.info(f"file path changed: {event.widget.path}")
        get_config_and_apply_to_tab(event.widget)


def on_new_tab(event: utils.EventWithData) -> None:
    tab = event.data_widget()
    if isinstance(tab, tabs.FileTab):
        # no need to run on_path_changed() now, <<WillOpenFile>> handles that
        tab.bind('<<PathChanged>>', on_path_changed, add=True)


def setup() -> None:
    utils.bind_with_data(get_tab_manager(), '<<WillOpenFile>>', before_file_opens, add=True)
    utils.bind_with_data(get_tab_manager(), '<<NewTab>>', on_new_tab, add=True)
