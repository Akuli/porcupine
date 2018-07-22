"""Stuff related to filetypes.ini."""

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


log = logging.getLogger(__name__)

_STUPID_DEFAULTS = '''\
# This is Porcupine's filetype configuration file. You can edit this file
# freely to suit your needs. Restart Porcupine to apply your changes to this
# file.
#
# Filetype names in [square brackets] can be anything you want, but note that
# some Porcupine plugins may expect specific names. For example, a
# Python-specific plugin might do nothing unless the current filetype's name is
# Python. The [Plain Text] section is special; if something is omitted in any
# other section, the [Plain Text] value will be used instead.
#
# Valid keys:
#   filename_patterns   space-separated list of patterns like *.py or *.txt
#   mimetypes           space-separated list of MIME types
#   shebang_regex       regular expression for shebangs
#   pygments_lexer      for syntax highlighting, see below
#   tabs2spaces         yes or no
#   indent_size         number of spaces or tab width, positive integer
#   max_line_length     positive integer or 0 for no limit
#   compile_command     see below
#   run_command         see below
#   lint_command        see below
#
# As you can see, Porcupine can detect the correct filetype based on the
# filename, MIME type or shebang. Use filename_patterns if you don't know what
# MIME types, shebangs and regexes are; * means anything, so '*.txt' means
# anything that ends with '.txt'.
#
# The shebang regex can contain anything accepted by Python's re module that
# matches any part of a shebang, or empty for no shebang checking. If you want
# to match the full shebang including the #! part, put it between ^ and $
# characters. Run help('re') in Python for more info about Python's regexes.
# Arguments starting with - are removed from the shebang before checking, so a
# regex like '^#!/blah/blah$' matches the shebang '#!/blah/blah --wat'.
#
# If no matching filetype is found but the Pygments highlighting library (see
# below) knows something about the file, Porcupine uses it and values in the
# [Plain Text] section. Porcupine displays these filetypes with ' (not from
# filetypes.ini)' at the end of their names. The [Plain Text] section is used if
# Pygments knows nothing about the file.
#
# Set pygments_lexer_name to pygments.lexers.SomethingLexer or the full name of
# any other Pygments lexer class. Note that Pygments lets you omit the part
# after pygments.lexers, e.g. pygments.lexers.Python3Lexer is equivalent to
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
#   tar cf {no_ext}.tar {file}
#
# ...is equivalent to this command:
#
#   tar cf "hello world.tar" "hello world.txt"
#

[Plain Text]
# indentation settings are like they are because most people like them this
# way, not because i like them this way
filename_patterns =
mimetypes =
shebang_regex =
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
shebang_regex = python(\d(\.\d)?)?$
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
filename_patterns = Makefile makefile Makefile.* makefile.*
pygments_lexer = pygments.lexers.MakefileLexer
# make doesn't work with spaces
tabs2spaces = no
run_command = make

# TODO: Windows batch files and powershell files
# i'm not trying to discriminate anyone with pygments_lexer and
# run_command, change them if you want to
# shebang_regex is partly copy/pasted from nano's default config
[Shell]
filename_patterns = *.sh
shebang_regex = ((ba|da|k|pdk)?sh[-0-9_]*|openrc-run|runscript)$
pygments_lexer = pygments.lexers.BashLexer
run_command = bash {file}

# tcl man pages and many people on wiki.tcl.tk indent with 3 spaces
[Tcl]
mimetypes = text/x-tcl text/x-script.tcl application/x-tcl
shebang_regex = (wi|tcl)sh$
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

# on startup, all file types specified in the config file are loaded to
# _config and _filetypes, and new filetypes are added to them if the
# user opens a file that doesn't match any of the existing file types
# _config is never saved back to filetypes.ini
#
# interpolation=None allows using % signs in the config
_config = configparser.ConfigParser(
    interpolation=None, default_section='Plain Text')

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
        assert name not in _filetypes
        section = _config[name]
        self.name = name
        self.filename_patterns = section['filename_patterns'].split()
        self.mimetypes = section['mimetypes'].split()

        # this is kind of verbose, but not too bad imo

        if section['shebang_regex']:
            try:
                self.shebang_regex = re.compile(section['shebang_regex'])
            except re.error as e:
                raise _OptionError('shebang_regex') from e
        else:
            self.shebang_regex = re.compile(r'this regex matches nothing^')

        try:
            modulename, classname = section['pygments_lexer'].rsplit('.', 1)
            module = importlib.import_module(modulename)
            self._pygments_lexer_class = getattr(module, classname)
        # this can import arbitrary modules, anything can go wrong
        except Exception as e:
            raise _OptionError('pygments_lexer') from e

        try:
            self.tabs2spaces = section.getboolean('tabs2spaces')
            assert self.tabs2spaces is not None
        except ValueError as e:
            raise _OptionError('tabs2spaces') from e

        try:
            self.indent_size = section.getint('indent_size')
            assert self.indent_size is not None
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
    except OSError:
        # the file doesn't exist yet
        pass

    try:
        # the shebang is read as utf-8 because the filetype config file
        # is utf-8
        with open(filename, 'r', encoding='utf-8') as file:
            if file.read(2) == '#!':
                # it has a shebang: read until \n but at most 1000
                # bytes, remove trailing whitespace
                shebang_line = '#!' + file.readline(1000).rstrip()
            else:
                shebang_line = None
    except (UnicodeError, OSError):
        shebang_line = None

    if shebang_line is not None:
        # remove arguments: "#!/bla/bla -t --bleh" becomes "#!/bla/bla"
        shebang_line = re.sub(r'\s-.*$', '', shebang_line)

    mimetype = mimetypes.guess_type(urllib.request.pathname2url(filename))[0]

    for filetype in _filetypes.values():
        if mimetype in filetype.mimetypes:
            return filetype
        if any(fnmatch.fnmatch(os.path.basename(filename), pattern)
               for pattern in filetype.filename_patterns):
            return filetype
        if (filetype.shebang_regex is not None and
                shebang_line is not None and
                filetype.shebang_regex.search(shebang_line) is not None):
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
            # can we use the shebang?
            if shebang_line is None:
                return _filetypes['Plain Text']
            lexer = pygments.lexers.guess_lexer(shebang_line)
            if isinstance(lexer, pygments.lexers.TextLexer):
                return _filetypes['Plain Text']

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


def _add_missing_mimetypes():
    # many of these are missing on windows
    need_to_know = {
        # extension: possible_mimetype
        # if the extension is detected as some other mime type it's ok
        # unless this is running on windows and that other mime type is
        # 'text/plain' because by default, windows detects e.g. .py
        # files as 'text/plain'
        '.py': 'text/x-python',
        '.c': 'text/x-csrc',
        '.h': 'text/x-chdr',
        '.c++': 'text/x-c++src',
        '.cpp': 'text/x-c++src',
        '.cxx': 'text/x-c++src',
        '.cc': 'text/x-c++src',
        '.h++': 'text/x-c++hdr',
        '.hpp': 'text/x-c++hdr',
        '.hxx': 'text/x-c++hdr',
        '.hh': 'text/x-c++hdr',
        '.java': 'text/x-java',
        '.js': 'application/javascript',
        '.sh': 'application/x-sh',
        '.tcl': 'application/x-tcl',
        '.json': 'application/json',
    }

    for extension, mimetype in need_to_know.items():
        guess = mimetypes.guess_type('whatever' + extension)[0]
        if guess is None or (platform.system() == 'Windows' and
                             guess == 'text/plain'):
            log.debug('adding MIME type %r for extension %r',
                      mimetype, extension)
            mimetypes.add_type(mimetype, extension)


def _init():
    assert (not _filetypes), "cannot _init() twice"
    _add_missing_mimetypes()
    stupid = configparser.ConfigParser(default_section='Plain Text')
    stupid.read_string(_STUPID_DEFAULTS)

    log.debug("trying to load '%s'", _get_ini_path())
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
    else:
        # neither of the except things ran, everything succeeded
        # now we get to take care of some backwards compatibility stuff :D

        # in the past, Porcupine used 'DEFAULT' instead of 'Plain Text'
        if 'DEFAULT' in _config:
            log.warning("filetypes.ini contains a deprecated [DEFAULT] "
                        "section, consider renaming it to [Plain Text]")
            # _config.pop seems to be broken
            plain_text = dict(_config['DEFAULT'])
            del _config['DEFAULT']
            _config['Plain Text'] = plain_text

        # old porcupines created config files that didn't have all the
        # keys they need to have for this porcupine
        # stupid['Plain Text'] and _config['Plain Text'] behave like dicts
        missing_keys = set(stupid['Plain Text']) - set(_config['Plain Text'])
        if missing_keys:
            log.error("the [Plain Text] section in filetypes.ini does not "
                      "contain %s, Porcupine's defaults will be used for "
                      "missing keys", ', '.join(missing_keys))

            # _config is already loaded from filetypes.ini, so must make
            # sure anything that came from there is not overrided: read
            # the stupid defaults first and override with filetypes.ini
            # duck-typing: configparsers behave like dicts
            merger = configparser.ConfigParser(default_section='Plain Text')
            merger.read_dict(stupid)
            merger.read_dict(_config)
            _config.read_dict(merger)
        else:
            log.debug("loaded filetypes.ini successfully")

    # file types are displayed in the menu, and / is a special character in
    # menu items
    for section_name in _config.sections():
        if '/' in section_name:
            log.warning(
                "%r is not a valid filetype name because it contains a /",
                section_name)

            # _config.pop(section_name) doesn't work for some reason
            section = dict(_config[section_name])
            del _config[section_name]
            _config[section_name.replace('/', '_')] = section

    # make sure that the Plain Text section is first, its values must be
    # valid when validating other sections
    for section_name in (['Plain Text'] + _config.sections()):
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
                if section_name == 'Plain Text':
                    stupid = configparser.ConfigParser(
                        default_section='Plain Text')
                    stupid.read_string(_STUPID_DEFAULTS)
                    _config['Plain Text'][str(e)] = stupid['Plain Text'][str(e)]
                else:
                    del _config[section_name][str(e)]  # use Plain Text's value
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
# FIXME: this is outdated >:(
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
