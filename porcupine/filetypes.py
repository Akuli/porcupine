"""Stuff related to filetypes.toml."""
# TODO: replace all this with editorconfig

import fnmatch
import logging
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import pygments.lexer   # type: ignore
import pygments.lexers  # type: ignore
import pygments.token   # type: ignore
from pygments.util import ClassNotFound     # type: ignore
import toml

# 'import porcupine' is for porcupine.get_main_window(), can't use a from
# import because import cycles
import porcupine
from porcupine import dirs


log = logging.getLogger(__name__)
_filetypes: Dict[str, Dict[str, Any]] = {}


def _no_detecting_stuff(filetype: Dict[str, Any]) -> Dict[str, Any]:
    result = filetype.copy()
    del result['filename_patterns']
    del result['shebang_regex']
    return result


def _get_filetype_from_matches(
    matches: Dict[str, Dict[str, Any]],
    they_match_what: str,
) -> Optional[Dict[str, Any]]:
    if not matches:
        return None

    [result, *rest] = matches.values()
    if rest:
        names = ', '.join(matches.keys())
        log.warning(f"multiple file types match {they_match_what}: {names}")
    return _no_detecting_stuff(result)


def _guess_by_filename(filepath: pathlib.Path) -> Optional[Dict[str, Any]]:
    return _get_filetype_from_matches({
        name: filetype
        for name, filetype in _filetypes.items()
        if any(
            fnmatch.fnmatch(filepath.name, pat)
            for pat in filetype['filename_patterns']
        )
    }, f"filename {filepath.name!r}")


def _guess_by_shebang(content_start: str) -> Optional[Dict[str, Any]]:
    shebang_line = content_start.split('\n')[0]
    matches: Dict[str, Dict[str, Any]] = {}

    for name, filetype in _filetypes.items():
        if re.search(filetype['shebang_regex'], shebang_line) is not None:
            matches[name] = filetype

    return _get_filetype_from_matches(matches, f"shebang {shebang_line!r}")


# TODO: take content as argument
def guess_filetype(filepath: pathlib.Path) -> Dict[str, Any]:
    """Return a filetype dict for a file name.

    Sometimes nothing in the ``filetypes.toml`` configuration matches the file
    type but Pygments is still able to guess some information about the file.
    In those cases, the returned filetype dict can't be accessed with
    :func:`get_filetype_by_name`.
    """
    filetype = _guess_by_filename(filepath)
    if filetype is not None:
        return filetype

    try:
        # the shebang is read as utf-8 because the filetype config file
        # is utf-8
        with filepath.open('r', encoding='utf-8') as file:
            # don't read the entire file if it's huge
            shebang_line = file.readline(1000)
    except (UnicodeError, OSError):
        pass
    else:
        filetype = _guess_by_shebang(shebang_line)
        if filetype is not None:
            return filetype

    # if nothing else works, create a new filetype automagically based on pygments
    try:
        lexer = pygments.lexers.get_lexer_for_filename(filepath)
    except ClassNotFound:
        if shebang_line is None:
            return _filetypes['Plain Text']  # give up
        lexer = pygments.lexers.guess_lexer(shebang_line)
        if isinstance(lexer, pygments.lexers.TextLexer):
            return _filetypes['Plain Text']  # give up

    return {
        'pygments_lexer': type(lexer).__module__ + '.' + type(lexer).__name__,
    }


def get_filetype_by_name(name: str) -> Dict[str, Any]:
    """
    Find and return a filetype dict by the name between ``[`` and ``]`` in the
    config file.
    """
    return _filetypes[name]


def get_filetype_names() -> List[str]:
    """Return the names of all filetypes in the configuration files.

    The returned list doesn't change while Porcupine is running.
    """
    return list(_filetypes.keys())


def get_filedialog_kwargs() -> Dict[str, Any]:
    """This is a way to run tkinter dialogs that display the filetypes and ext\
ensions that Porcupine supports.

    This function returns a dictionary of keyword arguments suitable for
    functions in ``tkinter.filedialog``. Example::

        from tkinter import filedialog
        from porcupine.filetypes import get_filedialog_kwargs

        filenames = filedialog.askopenfilenames(**get_filedialog_kwargs())
        for filename in filenames:
            print("Opening", filename)

    You can use this function with other ``tkinter.filedialog`` functions as
    well.
    """
    result: List[Tuple[
        str,
        Union[str, Tuple[str, ...]],  # tkinter works this way
    ]] = [("All files", "*")]
    for name in get_filetype_names():
        result.append((name, tuple(get_filetype_by_name(name)['filename_patterns'])))

    widget = porcupine.get_main_window()   # any widget would do
    if len(result) == 1 and widget.tk.call('tk', 'windowingsystem') == 'aqua':
        # there's a bug that makes python crash with this list on osx, and osx
        # creates a huge error message that complains about an empty parameter
        # list... so it seems like osx ignores ("All files", "*") and disallows
        # empty filetypes lists
        #
        # TODO: is this actually a problem with modern Tcl/Tk versions? I don't
        # have a mac, and the above text was written after helping someone else
        # to debug a different tkinter program on IRC.
        return {}
    return {'filetypes': result}


def _is_list_of_strings(obj: object) -> bool:
    return isinstance(obj, list) and all(isinstance(item, str) for item in obj)


def _init() -> None:
    if _filetypes:
        # already inited, __main__.py needs to init filetypes before gui stuff
        return

    user_path = dirs.configdir / 'filetypes.toml'
    defaults_path = pathlib.Path(__file__).absolute().parent / 'default_filetypes.toml'

    it_succeeded = False
    try:
        # toml.load seems to merge the configs quite nicely
        # TODO: create typeshed issue about how these don't actually need to be strings
        _filetypes.update(toml.load([str(defaults_path), str(user_path)]))
        it_succeeded = True
    except FileNotFoundError:
        log.info(f"'{user_path}' doesn't exist yet, creating it")
        with user_path.open('x') as file:
            file.write('''\
# Putting filetype configuration into this file overrides Porcupine's default
# filetype configuration. You can read the default configuration here:
#
#    https://github.com/Akuli/porcupine/blob/master/porcupine/default_filetypes.toml
''')
    except (OSError, UnicodeError, toml.TomlDecodeError):
        log.exception(f"reading '{user_path}' failed")

    if not it_succeeded:
        # read defaults and ignore whatever user configured
        _filetypes.update(toml.load(defaults_path))

    # everything except filename_patterns and shebang_regex is handled by Settings objects
    for name, filetype in _filetypes.items():
        if ('filename_patterns' in filetype and
                not _is_list_of_strings(filetype['filename_patterns'])):
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
