# TODO: document the filetypes.ini file somewhere
import configparser
import logging
import os
import platform
import re
import shutil
import subprocess
import sys

import pygments.lexers

from porcupine import dirs, utils

log = logging.getLogger(__name__)


# TODO: better pickle support
class FileType:
    """The type of values of :data:`filetypes`.

    Don't create FileType objects yourself. Porcupine loads all Pygments
    lexers into :data:`filetypes` by default, so it's best to `create a
    Pygments lexer <http://pygments.org/docs/lexerdevelopment/>`_ instead.

    FileType objects have these attributes:

    :attr name:
        Human-readable name for the file type, e.g. ``'JavaScript'``.
        These are also used as keys in :data:`filetypes`.
    :attr patterns:
        List of :mod:`fnmatch` compatible filename patterns. For
        example, ``['*.js'}``.
    :attr mimetypes:
        List of mimetype strings, e.g.
        ``['application/x-javascript', 'text/x-javascript']``.
    :attr tabs2spaces:
    :attr indent_size:
    :attr max_line_length:
    :attr compile_command:
    :attr run_command:
    :attr lint_command:
        These attributes come from `filetypes.ini`_.
    """

    __slots__ = ('name', 'patterns', 'mimetypes',
                 '_lexer_name', '_lexer_options',
                 'tabs2spaces', 'indent_size', 'max_line_length',
                 'compile_command', 'run_command', 'lint_command')
    _DEFAULT_OPTIONS = {
        'tabs2spaces': True,
        'indent_size': 4,
        'max_line_length': 0,
        'compile_command': '',
        'run_command': '',
        'lint_command': '',
    }

    def __init__(self, name, lexer_name, lexer_options, patterns, mimetypes):
        self.name = name
        self._lexer_name = lexer_name
        self._lexer_options = lexer_options
        self.patterns = list(patterns)
        self.mimetypes = list(mimetypes)
        for name, value in self._DEFAULT_OPTIONS.items():
            setattr(self, name, value)

    def get_lexer(self):
        """Return a Pygments lexer object for files of this type."""
        return pygments.lexers.get_lexer_by_name(
            self._lexer_name, **self._lexer_options)

    def _get_options(self):
        return {name: getattr(self, name) for name in self._DEFAULT_OPTIONS}

    @staticmethod
    def substitute_command(template, file):
        """
        Format a command for Windows command prompt or a POSIX -compatible
        shell.

        :param template: A value of *compile_command*, *run_command* or
                         *lint_command*.
        """
        return template.format(
            file=utils.quote(file),
            no_ext=utils.quote(os.path.splitext(file)[0]),
            no_exts=utils.quote(re.search(r'^\.*[^\.]*', file).group(0)),
        )


filetypes = {}       # {filetype.name: filetype}


def lexer2filetype(lexer):
    """Return a FileType object that matches a Pygments lexer.

    The lexer can be a lexer class or an instance of a lexer class.

    This is useful because the ``pygments.lexers`` module contains
    `many handy functions for finding the right lexer
    <http://pygments.org/docs/api/#module-pygments.lexers>`_.
    """
    # sometimes pygments uses python 3 lexer correctly and we must not
    # do weird workarounds
    if lexer.name == 'Python 3':
        return filetypes['Python']
    if lexer.name == 'Python 3.0 Traceback':
        return filetypes['Python Traceback']
    return filetypes[lexer.name]


# i experimented with using mimetypes.guess_all_extensions() and the
# pygments mimetypes to get even more filename patterns, but that sucked
# because '.c' is a 'text/plain' extension according to the mimetypes module
def _init_filetypes_from_lexers():
    for name, aliases, patterns, mimetypes in pygments.lexers.get_all_lexers():
        # pygments hates python 3 :(
        if name in {'Python', 'Python Traceback'}:     # these are python 2
            continue

        lexer_options = {}
        if name == 'Python 3':
            name = 'Python'
            aliases += tuple(pygments.lexers.PythonLexer.aliases)
            patterns += tuple(pygments.lexers.PythonLexer.filenames)
            mimetypes += tuple(pygments.lexers.PythonLexer.mimetypes)
        elif name == 'Python 3.0 Traceback':   # not really specific to 3.0
            name = 'Python Traceback'
            aliases += tuple(pygments.lexers.PythonTracebackLexer.aliases)
            patterns += tuple(pygments.lexers.PythonTracebackLexer.filenames)
            mimetypes += tuple(pygments.lexers.PythonTracebackLexer.mimetypes)
        elif name == 'Python console session':
            lexer_options['python3'] = True

        # longer name aliases are less likely to conflict with each other
        lexer_name = max(aliases, key=len)
        filetypes[name] = FileType(
            name, lexer_name, lexer_options, patterns, mimetypes)


def _find_short_python_command():
    if platform.system() == 'Windows':
        # windows python uses a py.exe launcher program in system32
        expected = 'Python %d.%d.%d' % sys.version_info[:3]
        try:
            for python in ['py', 'py -%d' % sys.version_info[0],
                           'py -%d.%d' % sys.version_info[:2]]:
                # command strings aren't different than lists of
                # arguments on windows, the subprocess module just
                # quotes lists anyway (see subprocess.list2cmdline)
                got = subprocess.check_output('%s --version' % python)
                if expected.encode('ascii') == got.strip():
                    return python
        except (OSError, subprocess.CalledProcessError):
            # something's wrong with py.exe 0_o it probably doesn't
            # exist at all and we got a FileNotFoundError
            pass

    else:
        for python in ['python', 'python%d' % sys.version_info[0],
                       'python%d.%d' % sys.version_info[:2]]:
            # os.path.samefile() does the right thing with symlinks
            path = shutil.which(python)
            if path is not None and os.path.samefile(path, utils.python):
                return python

    # use full path as a fallback
    return utils.python


def _set_stupid_defaults():
    # TODO: this assumes mingw in %PATH% on windows :D
    compiled = ('{no_ext}.exe' if platform.system() == 'Windows'
                else './{no_ext}')
    template = '%s {file} -Wall -Wextra -std=c99 -o ' + compiled
    for language, compiler in [('C', 'cc'), ('C++', 'c++')]:
        filetypes[language].compile_command = template % compiler
        filetypes[language].run_command = compiled

    # TODO: something nicer for finding node
    filetypes['JavaScript'].indent_size = 2
    if os.path.isfile('/etc/debian_version'):
        filetypes['JavaScript'].run_command = 'nodejs {file}'
    else:
        filetypes['JavaScript'].run_command = 'node {file}'

    filetypes['Makefile'].tabs2spaces = False

    python = _find_short_python_command()
    filetypes['Python'].max_line_length = 79
    filetypes['Python'].run_command = '%s {file}' % python
    filetypes['Python'].lint_command = '%s -m flake8 {file}' % python

    # 79 comes from documentation-style-guide-sphinx.readthedocs.io
    filetypes['reStructuredText'].indent_size = 3
    filetypes['reStructuredText'].max_line_length = 79


def _from_config(parser):
    for section_name in parser.sections():     # doesn't include 'Default'
        section = parser[section_name]
        try:
            filetype = filetypes[section_name]
        except KeyError:
            log.warning("unknown filetype %r in filetypes.ini", section_name)
            continue

        for name in section.keys():
            try:
                if name == 'tabs2spaces':
                    value = section.getboolean(name)
                elif name == 'indent_size':
                    value = section.getint(name)
                    if value <= 0:
                        raise ValueError
                elif name == 'max_line_length':
                    value = section.getint(name)
                    if value < 0:
                        raise ValueError
                elif name in {'compile_command', 'run_command',
                              'lint_command'}:
                    value = section[name]
                else:
                    log.warning("unknown option %r in %r", name, section_name)
                    continue
                setattr(filetype, name, value)

            except ValueError:
                log.warning("invalid %r value %r in %r",
                            name, section[name], section_name)


# TODO: add a link to porcupine's docs about this file when the docs are
# ready for it
_comments = '''\
# This is Porcupine's filetype configuration file. You can edit this
# file freely to suit your needs.
#
# For example, here's Linus Torvalds style settings for C files, with
# clang for compiling and include-what-you-use for linting:
#
#    [C]
#    tabs2spaces = no
#    indent_size = 8
#    max_line_length = 80
#    compile_command = clang {file} -Wall -Wextra -std=c99 -o {no_ext}
#    run_command = ./{no_ext}
#    lint_command = include-what-you ./{no_ext}
#
# I have never actually used include-what-you-use, so the lint command
# might be incorrect. But you get the idea.
'''


def init():
    """Set default filetypes to :data:`filetypes`."""
    assert (not filetypes), "cannot init() twice"
    _init_filetypes_from_lexers()
    _set_stupid_defaults()

    config_file = os.path.join(dirs.configdir, 'filetypes.ini')
    parser = configparser.ConfigParser(interpolation=None)

    try:
        # parser.read() suppresses exceptions
        with open(config_file, 'r') as f:
            parser.read_file(f)
    except FileNotFoundError:
        log.info("filetypes.ini not found, creating it")
        with open(config_file, 'w') as f:
            print(_comments, file=f)
    except (OSError, UnicodeError, configparser.Error) as err:
        # full tracebacks are ugly and this is supposed to be visible to users
        log.warning("%s in filetypes.ini: %s\n", type(err).__name__, err)
        return
