"""Everything related to filetypes.ini."""
# TODO: support shebangs like a modern editor should??

import collections
import configparser
import fnmatch
import importlib
import itertools
import logging
import mimetypes
import os
import platform
import re
import shlex
import traceback
import urllib.request   # for pathname2url, mimetypes wants urls

import pygments.lexer
import pygments.lexers
import pygments.token
import pygments.util     # for ClassNotFound

from porcupine import dirs, utils


_STUPID_DEFAULTS = '''\
# This is Porcupine's filetype configuration file. You can edit this file
# freely to suit your needs. Restart Porcupine to apply your changes to this
# file.
#
# Filetype names in [square brackets] can be anything you want, but note that
# some Porcupine plugins may expect specific names. For example, a
# Python-specific plugin might do nothing unless the current filetype's name is
# Python. The [DEFAULT] section is special; if something is omitted in any
# other section, the [DEFAULT] value will be used instead.
#
# Valid keys:
#   filename_patterns   space-separated list of patterns like *.py or *.txt
#   mimetypes           space-separated list of MIME types
#   pygments_lexer      for syntax highlighting, see below
#   tabs2spaces         yes or no
#   indent_size         number of spaces or tab width, positive integer
#   max_line_length     positive integer or 0 for no limit
#   compile_command     see below
#   run_command         see below
#   lint_command        see below
#
# If any of these are not specified, the values in the [DEFAULT] section will
# be used instead.
#
# As you can see, Porcupine can detect the correct filetype based on the
# filename or the MIME type. You can just use filename_patterns if you don't
# know what MIME types are. If no matching filetype is found but the Pygments
# highlighting library (see below) knows something about the file, Porcupine
# uses it and values in the [DEFAULT] section. The [DEFAULT] section will be
# used if Pygments knows nothing about the file.
#
# Set pygments_lexer_name to pygments.lexers.SomethingLexer or the full name of
# any other importable Python class. Note that Pygments lets you omit the part
# after pygments.lexers; e.g. pygments.lexers.Python3Lexer is equivalent to
# pygments.lexers.python.Python3Lexer. Here's a list of lexers that Pygments
# comes with:  http://pygments.org/docs/lexers/
#
# These substitutions are performed to the commands:
#   {file}      path to source file, e.g. "hello world.tar.gz"
#   {no_ext}    {file} without last extension, e.g. "hello world.tar"
#   {no_exts}   {file} without any extensions, e.g. "hello world"
#   {{          literal {
#   }}          literal }
#
# Redirections like > or | don't work. The command is split into an argument
# list before substituting in the filenames, so spaces in filenames don't cause
# issues. For example, if {file} is 'hello world.txt', then this...
#
#   tar -cf {no_ext}.tar {file}
#
# ...is equivalent to this command:
#
#   tar cf "hello world.tar" "hello world.txt"
#

[DEFAULT]
# indentation settings are like they are because most people like them this
# way, not because i like them this way
filename_patterns =
mimetypes =
pygments_lexer = pygments.lexers.TextLexer
tabs2spaces = yes
indent_size = 4
max_line_length = 0
compile_command =
run_command =
lint_command =

[Python]
mimetypes = text/x-python application/x-python text/x-python3 application/x-py\
thon3
pygments_lexer = pygments.lexers.Python3Lexer

# pep8-based brainwashing: KITTENS DIE IF YOU USE WRONG STYLE
tabs2spaces = yes
indent_size = 4
max_line_length = 79

# flake8 is the default because pylint doesn't like my code :/ </3
run_command = %(python)s {file}
lint_command = %(python)s -m flake8 {file}

# any style settings for some of these freely indentable languages would make
# some people hate me
[C]
mimetypes = text/x-csrc text/x-chdr
pygments_lexer = pygments.lexers.CLexer
compile_command = cc {file} -Wall -Wextra -std=c99 -o %(exe)s
run_command = %(runexe)s

[C++]
mimetypes = text/x-c++hdr text/x-c++src
pygments_lexer = pygments.lexers.CppLexer
compile_command = c++ {file} -Wall -Wextra --std=c++98 -o %(exe)s
run_command = %(runexe)s

[Java]
mimetypes = text/x-java
pygments_lexer = pygments.lexers.JavaLexer
compile_command = javac {file}
run_command = java {no_ext}

# almost everyone seems to use 2 space indents in javascript
[JavaScript]
mimetypes = application/javascript application/x-javascript text/javascript te\
xt/x-javascript
pygments_lexer = pygments.lexers.JavascriptLexer
tabs2spaces = yes
indent_size = 2
run_command = node {file}

[Makefile]
# python doesn't seem to support a Makefile mimetype by default
filename_patterns = Makefile makefile Makefile.* makefile.*
pygments_lexer = pygments.lexers.MakefileLexer
# make doesn't work with spaces
tabs2spaces = no
run_command = make

# TODO: Windows batch files and powershell files

# TODO: this really needs a shebang when porcupine will support them
# i'm not trying to discriminate anyone with pygments_lexer and
# run_command, change them if you want to
[Shell]
filename_patterns = *.sh
pygments_lexer = pygments.lexers.BashLexer
run_command = bash {file}

# tcl man pages and many people on wiki.tcl.tk indent with 3 spaces
[Tcl]
mimetypes = text/x-tcl text/x-script.tcl application/x-tcl
pygments_lexer = pygments.lexers.TclLexer
indent_size = 3
tabs2spaces = yes
run_command = tclsh {file}

[JSON]
mimetypes = application/json
pygments_lexer = pygments.lexers.JsonLexer
indent_size = 4
tabs2spaces = yes

# there are no official mime types for rst or markdown
[reStructuredText]
filename_patterns = *.rst
pygments_lexer = pygments.lexers.RstLexer

[Markdown]
filename_patterns = *.md *.markdown
mimetypes = text/x-markdown
pygments_lexer = pygments.lexers.MarkdownLexer
''' % {
    'python': utils.short_python_command,
    'exe': '{no_ext}.exe' if platform.system() == 'Windows' else '{no_ext}',
    'runexe': ('{no_ext}.exe' if platform.system() == 'Windows'
               else './{no_ext}'),
}


log = logging.getLogger(__name__)

# on startup, all file types specified in the config file are loaded to
# _config and _filetypes, and new filetypes are added to them if the
# user opens a file that doesn't match any of the existing file types
# _config is never saved back to filetypes.ini
_config = configparser.ConfigParser()

# ordered to make sure that filetypes loaded from filetypes.ini are used
# when possible
_filetypes = collections.OrderedDict()     # {name: _FileType}


# this cannot be a global variable because tests load this module
# and THEN change dirs.configdir
def _get_ini_path():
    return os.path.join(dirs.configdir, 'filetypes.ini')


# _FileType.__init__ raises this, str()'ing this error returns an option name
class _OptionError(Exception):
    pass


class _FileType:

    def __init__(self, name):
        assert name not in _filetypes and name in _config
        section = _config[name]
        self.name = name
        self.filename_patterns = section['filename_patterns'].split()
        self.mimetypes = section['mimetypes'].split()

        # this is kind of verbose, but not too bad imo
        # unknown options are ignored, newer porcupines might have more
        # keys and this way it should be possible to use the same config
        # file painlessly with different porcupines

        try:
            modulename, classname = section['pygments_lexer'].rsplit('.', 1)
            module = importlib.import_module(modulename)
            self._pygments_lexer_class = getattr(module, classname)
        # this can import arbitrary modules, anything can go wrong
        except Exception as e:
            raise _OptionError('pygments_lexer') from e

        try:
            self.tabs2spaces = section.getboolean('tabs2spaces')
            if self.tabs2spaces is None:
                assert name == 'DEFAULT'
                raise ValueError("missing tabs2spaces")
        except ValueError as e:
            raise _OptionError('tabs2spaces') from e

        try:
            self.indent_size = section.getint('indent_size')
            if self.indent_size is None:
                assert name == 'DEFAULT'
                raise ValueError("missing tabs2spaces")
            if self.indent_size <= 0:
                raise ValueError("indent_size must be positive")
        except ValueError as e:
            raise _OptionError('indent_size') from e

        try:
            self.max_line_length = section.getint('max_line_length')
            if self.max_line_length < 0:
                raise ValueError("max_line_length must be 0 or positive")
        except ValueError as e:
            raise _OptionError('max_line_length') from e

        for something_command in ['compile_command', 'run_command',
                                  'lint_command']:
            if self.has_command(something_command):
                try:
                    self.get_command(something_command, 'whatever')
                # str.format seems to raise ValueError and KeyError
                except (KeyError, ValueError) as e:
                    raise _OptionError(something_command) from e

    # TODO: support passing more options in the config file
    def get_lexer(self, **kwargs):
        return self._pygments_lexer_class(**kwargs)

    def has_command(self, something_command):
        return bool(_config[self.name][something_command].strip())

    def get_command(self, something_command, basename):
        assert os.sep not in basename, "%r is not a basename" % basename
        template = _config[self.name][something_command]
        format_args = {
            'file': basename,
            'no_ext': os.path.splitext(basename)[0],
            'no_exts': re.search(r'^\.*[^\.]*', basename).group(0),
        }
        result = [part.format(**format_args) for part in shlex.split(template)]
        assert result
        return result


def guess_filetype(filename):
    """Return a filetype object for a file name."""
    try:
        if os.path.samefile(filename, _get_ini_path()):
            return _filetypes['Porcupine filetypes.ini']
    except FileNotFoundError:
        # the file doesn't exist yet
        pass

    mimetype = mimetypes.guess_type(urllib.request.pathname2url(filename))[0]
    for filetype in _filetypes.values():
        if mimetype in filetype.mimetypes:
            return filetype
        if any(fnmatch.fnmatch(filename, pattern)
               for pattern in filetype.filename_patterns):
            return filetype

    # create a new filetype automagically if nothing else works
    try:
        if mimetype is None:
            # this is the easiest way to handle this corner case i came
            # up with
            raise pygments.util.ClassNotFound
        lexer = pygments.lexers.get_lexer_for_mimetype(mimetype)
    except pygments.util.ClassNotFound:
        try:
            lexer = pygments.lexers.get_lexer_for_filename(filename)
        except pygments.util.ClassNotFound:
            # ok, there will be no highlighting with default settings
            return _filetypes['DEFAULT']

    name = lexer.name + ' (not from filetypes.ini)'
    if name in _filetypes:
        return _filetypes[name]

    _config[name] = {
        'filename_patterns': ' '.join(lexer.filenames),
        'mimetypes': ' '.join(lexer.mimetypes),
        'pygments_lexer': type(lexer).__module__ + '.' + type(lexer).__name__,
    }
    _filetypes[name] = _FileType(name)       # uses the _config
    return _filetypes[name]


def get_filetype_by_name(name):
    """Find and return a filetype object by its ``name`` attribute."""
    return _filetypes[name]


def get_all_filetypes():
    """Return a list of all loaded filetypes."""
    return list(_filetypes.values())


def _init():
    assert (not _filetypes), "cannot init() twice"

    # rest of this code doesn't check for missing values, so everything
    # must be set to something at least in DEFAULT
    stupid = configparser.ConfigParser()
    stupid.read_string(_STUPID_DEFAULTS)
    _config['DEFAULT'] = stupid['DEFAULT']

    try:
        # config.read() suppresses exceptions
        with open(_get_ini_path(), 'r', encoding='utf-8') as file:
            _config.read_file(file)
    except FileNotFoundError:
        # the config has nothing but the stupid defaults in it right now
        log.info("filetypes.ini not found, creating it")
        _config.read_string(_STUPID_DEFAULTS)
        with open(_get_ini_path(), 'w', encoding='utf-8') as file:
            file.write(_STUPID_DEFAULTS)
    except (OSError, UnicodeError, configparser.Error) as err:
        # full tracebacks are ugly and this is supposed to be visible to users
        log.error("%s in filetypes.ini: %s", type(err).__name__, err)
        log.debug("default filetypes will be used instead")
        log.debug("here's the full traceback", exc_info=True)
        _config.read_string(_STUPID_DEFAULTS)

    # make sure that the DEFAULT section is first, its values must be
    # valid when validating other sections
    for section_name in (['DEFAULT'] + _config.sections()):
        while True:
            try:
                filetype = _FileType(section_name)
            except _OptionError as e:
                # e.__cause__ is the error that option_error was raised in
                # _FileType.__init__, str(e) is the option name
                log.error("invalid %r value in [%s]", str(e), section_name)
                log.debug("here's the full traceback\n%s", ''.join(
                    traceback.format_exception(type(e.__cause__), e.__cause__,
                                               e.__cause__.__traceback__)))
                if section_name == 'DEFAULT':
                    stupid = configparser.ConfigParser()
                    stupid.read_string(_STUPID_DEFAULTS)
                    _config['DEFAULT'][str(e)] = stupid['DEFAULT'][str(e)]
                else:
                    del _config[section_name][str(e)]  # use DEFAULT's value
            else:
                _filetypes[section_name] = filetype
                break

    if 'Porcupine filetypes.ini' not in _filetypes:
        _config['Porcupine filetypes.ini'] = {
            'pygments_lexer': __name__ + '._FiletypesDotIniLexer',
        }
        _filetypes['Porcupine filetypes.ini'] = _FileType(   # stupid pep8 >:(
            'Porcupine filetypes.ini')


# unlike pygments.lexers.IniLexer, this highlights correct keys and
# values in filetypes.ini specially
class _FiletypesDotIniLexer(pygments.lexer.RegexLexer):

    # these are probably not needed
    name = 'Porcupine filetypes.ini'
    aliases = ['porcupine-filetypes']
    filenames = []

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
        [(r'\[(.*?)\]$', pygments.token.Keyword)],
        key_val_pair(r'filename_patterns', r'.*'),
        key_val_pair(r'mimetypes', r'.*'),      # TODO
        key_val_pair(r'pygments_lexer', r'.*'),      # TODO
        key_val_pair(r'tabs2spaces', r'yes|no'),
        key_val_pair(r'indent_size', r'[1-9][0-9]*'),        # positive int
        key_val_pair(r'max_line_length', r'0|[1-9][0-9]*'),  # non-negative int
        key_val_pair(r'(?:compile|run|lint)_command', r'.*'),   # TODO

        # less red error tokens
        key_val_pair(r'.*?', r'.*?', pygments.token.Text, pygments.token.Text),
        [(r'.+?$', pygments.token.Text)],
    ))}
