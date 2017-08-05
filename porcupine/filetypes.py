"""Everything related to filetypes.ini."""
import configparser
import functools
import itertools
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys

import pygments.lexer
import pygments.lexers
import pygments.token

from porcupine import dirs, utils

_FILETYPES_DOT_INI = os.path.join(dirs.configdir, 'filetypes.ini')
log = logging.getLogger(__name__)


class FileType:
    """The values of :data:`~filetypes` are FileType objects.

    Don't create filetype objects yourself. Porcupine loads all Pygments
    lexers into :data:`~filetypes` by default, so you should `create a
    Pygments lexer <http://pygments.org/docs/lexerdevelopment/>`_ instead.

    .. attribute:: name

        This attribute is always set to the key of :data:`filetypes` so
        that ``filetypes[some_file_type.name]`` should be always
        ``some_file_type``.

    .. attribute:: patterns

        List of :mod:`fnmatch` pattern strings, like ``'*.py'`` or
        ``'Makefile'``.

    .. attribute:: mimetypes

        List of mimetype strings, e.g.
        ``['application/x-javascript', 'text/x-javascript']``.

    .. attribute:: tabs2spaces
    .. attribute:: indent_size
    .. attribute:: max_line_length
    .. attribute:: compile_command
    .. attribute:: run_command
    .. attribute:: lint_command

        These attributes correspond to the values defined in
        ``filetypes.ini``. ``tabs2spaces`` is True or False, and the
        ``indent_size`` and ``max_line_length`` attributes are integers.
        The commands are strings and they may be empty.
    """

    __slots__ = ('name', 'patterns', 'mimetypes', '_lexer_getter',
                 'tabs2spaces', 'indent_size', 'max_line_length',
                 'compile_command', 'run_command', 'lint_command')

    def __init__(self, name, lexer_getter, patterns, mimetypes,
                 config_section):
        self.name = name
        self._lexer_getter = lexer_getter
        self.patterns = list(patterns)
        self.mimetypes = list(mimetypes)

        self.tabs2spaces = config_section.getboolean('tabs2spaces')
        self.indent_size = config_section.getint('indent_size')
        self.max_line_length = config_section.getint('max_line_length')
        self.compile_command = config_section['compile_command']
        self.run_command = config_section['run_command']
        self.lint_command = config_section['lint_command']

    def get_lexer(self):
        """Return a Pygments lexer object for files of this type."""
        return self._lexer_getter()

    @staticmethod
    def substitute_command(template, file):
        """Create an argument list for e.g. :func:`subprocess.call`.

        :param str template: A value of :attr:`.compile_command`,
                             :attr:`.run_command` or :attr:`.lint_command`.
        :param str file: Path to the source file, without quotes.
        :return: List of strings.
        """
        format_args = {
            'file': file,
            'no_ext': os.path.splitext(file)[0],
            'no_exts': re.search(r'^\.*[^\.]*', file).group(0),
        }

        # the template must be split into parts so that '{no_ext}.o'
        # turns into '"hello world.o"' when no_ext is 'hello world'
        # shlex.split supports single and double quotes
        return [part.format(**format_args)
                for part in shlex.split(template)]


filetypes = {}      # this is {filetype.name: filetype}, see init()


def guess_filetype(filename):
    """Return a FileType object based on a file name."""
    try:
        if os.path.samefile(filename, _FILETYPES_DOT_INI):
            return filetypes['Porcupine filetypes.ini']
    except FileNotFoundError:
        # the file doesn't exist yet
        pass

    # sometimes pygments uses python 3 lexer correctly and we must not
    # do weird workarounds
    temp_lexer = pygments.lexers.get_lexer_for_filename(filename)
    if temp_lexer.name == 'Python 3':
        return filetypes['Python']
    if temp_lexer.name == 'Python 3.0 Traceback':
        return filetypes['Python Traceback']
    return filetypes[temp_lexer.name]


def _find_short_python_command():
    if platform.system() == 'Windows':
        # windows python uses a py.exe launcher program in system32
        expected = 'Python %d.%d.%d' % sys.version_info[:3]
        try:
            for python in ['py', 'py -%d' % sys.version_info[0],
                           'py -%d.%d' % sys.version_info[:2]]:
                # command strings aren't different from lists of
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


# default values of the DEFAULT section
_DEFAULT_DEFAULTS = {
    'tabs2spaces': 'yes',
    'indent_size': '4',
    'max_line_length': '0',
    'compile_command': '',
    'run_command': '',
    'lint_command': '',
}


def _set_stupid_defaults(config):
    config['DEFAULT'] = _DEFAULT_DEFAULTS

    # TODO: this assumes mingw in %PATH% on windows :D
    # FIXME: c99 is probably not a valid c++ standard
    compiled = ('{no_ext}.exe' if platform.system() == 'Windows'
                else './{no_ext}')
    template = '%s {file} -Wall -Wextra -std=c99 -o ' + compiled
    for language, compiler in [('C', 'cc'), ('C++', 'c++')]:
        config[language] = {
            'compile_command': template % compiler,
            'run_command': compiled,
        }

    # TODO: something nicer for finding node
    config['JavaScript'] = {'indent_size': '2'}
    if os.path.isfile('/etc/debian_version'):
        config['JavaScript']['run_command'] = 'nodejs {file}'
    else:
        config['JavaScript']['run_command'] = 'node {file}'

    config['Makefile'] = {'tabs2spaces': 'no'}

    python = _find_short_python_command()
    config['Python'] = {
        'max_line_length': '79',
        'run_command': '%s {file}' % python,
        'lint_command': '%s -m flake8 {file}' % python,
    }

    # 79 comes from documentation-style-guide-sphinx.readthedocs.io
    config['reStructuredText'] = {
        'indent_size': '3',
        'max_line_length': '79'
    }


# unlike pygments.lexers.IniLexer, this highlights correct keys and
# values in filetypes.ini specially
class _FiletypesDotIniLexer(pygments.lexer.RegexLexer):
    name = 'Porcupine filetypes.ini'
    aliases = ['porcupine-filetypes']
    filenames = []      # see guess_filetype() above

    # this is done with a callback to allow creating this class without
    # calling init()
    def header_callback(lexer, match):
        # highlight correct filetype names specially
        if match.group(1) in filetypes or match.group(1) == 'DEFAULT':
            yield (match.start(), pygments.token.Keyword, match.group(0))
        else:
            yield (match.start(), pygments.token.Text, match.group(0))

    def key_val_pair(key, value, key_token=pygments.token.Name.Builtin,
                     value_token=pygments.token.String):
        for regex, token in [(value, value_token),
                             (r'.*?', pygments.token.Name)]:
            yield (
                r'(%s)([^\S\n]*)(=)([^\S\n]*)(%s)$' % (key, regex),
                pygments.lexer.bygroups(
                    key_token, pygments.token.Text,
                    pygments.token.Operator, pygments.token.Text, token))

    tokens = {'root': list(itertools.chain(
        [(r'\s*#.*?$', pygments.token.Comment)],
        [(r'\[(.*?)\]$', header_callback)],
        key_val_pair(r'tabs2spaces', r'yes|no'),
        key_val_pair(r'indent_size', r'[1-9][0-9]*'),        # positive int
        key_val_pair(r'max_line_length', r'0|[1-9][0-9]*'),  # non-negative int
        key_val_pair(r'(?:compile|run|lint)_command', r'.*'),
        key_val_pair(r'.*?', r'.*?', pygments.token.Text, pygments.token.Text),
        [(r'.+?$', pygments.token.Text)],       # less red error tokens
    ))}


# i experimented with using the mimetypes module and the pygments
# mimetypes to get even more filename patterns, but that sucked because
# '.c' is a 'text/plain' extension according to the mimetypes module
def _get_pygments_lexers():
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
        lexer_getter = functools.partial(
            pygments.lexers.get_lexer_by_name, lexer_name, **lexer_options)
        yield [name, lexer_getter, patterns, mimetypes]

    yield ['Porcupine filetypes.ini', _FiletypesDotIniLexer, (), ()]


def _validate_value(section_name, section, option, getter,
                    minimum=None, command=False):
    try:
        if getter is None:
            value = section[option]
        else:
            value = getter(option)

        if minimum is not None and value < minimum:
            raise ValueError
        if command:
            FileType.substitute_command(value, 'whatever.tar.gz')

    except ValueError:
        # the error might come from getter() or substitute_command()
        log.error("invalid %r value %r in [%s]",
                  option, section[option], section_name)
        if section_name == 'DEFAULT':
            section[option] = _DEFAULT_DEFAULTS[option]
        else:
            del section[option]        # use the DEFAULT section's value


# unknown sections and keys are intentionally ignored, newer porcupines
# might have more keys and this way the same config file can be used
# painlessly in different porcupine and pygments versions
def _config2filetypes(config):
    # make sure that 'DEFAULT' is first, its values must be valid when
    # _validate_value() is called with other sections
    for name in (['DEFAULT'] + config.sections()):
        section = config[name]
        validate = functools.partial(_validate_value, name, section)
        validate('tabs2spaces', section.getboolean)
        validate('indent_size', section.getint, minimum=1)
        validate('max_line_length', section.getint, minimum=0)
        validate('compile_command', None, command=True)
        validate('run_command', None, command=True)
        validate('lint_command', None, command=True)

    for name, *args in _get_pygments_lexers():
        # setdefault return value is useless, this is a small bug
        config.setdefault(name, {})
        all_args = [name] + args + [config[name]]
        yield FileType(*all_args)


# TODO: add a link to porcupine's docs about this file when the docs are
# ready for it
_comments = '''\
# This is Porcupine's filetype configuration file. You can edit this
# file freely to suit your needs.
#
# Valid keys:
#   tabs2spaces         yes or no
#   indent_size         number of spaces or tab width, positive integer
#   max_line_length     positive integer or 0 for no limit
#   compile_command     see below
#   run_command         see below
#   lint_command        see below
#
# If any of these are not specified, the values in the DEFAULT section
# will be used instead.
#
# The command options will be executed in %(cmd or shell)s. These
# substitutions are performed (file paths are quoted correctly):
#   {file}      path to source file, e.g. "hello world.tar.gz"
#   {no_ext}    {file} without last extension, e.g. "hello world.tar"
#   {no_exts}   {file} without any extensions, e.g. "hello world"
#
# Restart Porcupine to apply your changes to this file.
''' % {'cmd or shell': ('command prompt' if platform.system() == 'Windows'
                        else 'bash')}


def init():
    """Create :class:`FileType` objects and add them to :data:`~filetypes`."""
    assert (not filetypes), "cannot init() twice"

    config = configparser.ConfigParser(interpolation=None)
    _set_stupid_defaults(config)

    try:
        # config.read() suppresses exceptions
        with open(_FILETYPES_DOT_INI, 'r', encoding='utf-8') as f:
            config.read_file(f)
    except FileNotFoundError:
        # the config has nothing but the stupid defaults in it right now
        log.info("filetypes.ini not found, creating it")
        with open(_FILETYPES_DOT_INI, 'w', encoding='utf-8') as f:
            print(_comments, file=f)
            config.write(f)
    except (OSError, UnicodeError, configparser.Error) as err:
        # full tracebacks are ugly and this is supposed to be visible to users
        log.error("%s in filetypes.ini: %s", type(err).__name__, err)
        log.debug("here's the full traceback", exc_info=True)

    filetypes.update({filetype.name: filetype
                      for filetype in _config2filetypes(config)})
