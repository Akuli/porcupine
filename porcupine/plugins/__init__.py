"""Plugin system for Porcupine.

Porcupine comes with many handy plugins, and you can read them to
get an idea of how everything works. You can find them like this:

    >>> import porcupine.plugins
    >>> porcupine.plugins.__path__
    ['/home/akuli/.config/porcupine/plugins',
     '/bla/bla/bla/porcupine/plugins']
    >>>

You can add your own plugins to the first directory and Porcupine's
default plugins are installed in the second directory.

Plugins are just Python files that Porcupine imports on startup, so
their names need to be valid module names. The files should import
porcupine and call porcupine.plugins.add_plugin(). You can read the
default plugins for examples.

Some notes about writing plugins:

  - If you don't like a default plugin you can disable that by creating
    an empty file with the same name in your own plugin directory.

  - Use the add keyword argument to bind() when binding widgets that
    Porcupine created. See the help, e.g. help('tkinter.Label.bind').
    This way other plugins can bind the same event too. If you need to
    return 'break' from a bind callback the all argument does nothing
    and you just need to hope for the best.

  - Sometimes multiple plugins need to bind something and return
    'break', or multiple plugins need to calculate the same thing in the
    bind() callback. Porcupine often uses lists of callbacks in these
    cases. For example, <<Modified>> needs to be handled in one place
    only so porcupine.textwidget.Text has an on_modified callback list.
    But it offers other handy callback lists too. For example, the
    statusbar needs to be updated when the cursor moves so there's an
    on_cursor_move callback list.

When you have added a plugin file, run Porcupine from a terminal,
command prompt or PowerShell so you'll see any errors messages that your
plugin might produce. Note that you don't need to save all files you
have opened in Porcupine; there's nothing wrong with running multiple
Porcupines at the same time.
"""

import importlib
import logging
import os
import random
import types

import porcupine


# simple hack to allow user-wide plugins
__path__.insert(0, porcupine.dirs.userplugindir)

# __path__ will show up in help() too because the module docstring
# recommends checking it out
__all__ = ['add_plugin', '__path__']

log = logging.getLogger(__name__)
plugins = []


def _do_nothing(*args):
    pass


def add_plugin(name, *, start_callback=_do_nothing, filetab_hook=_do_nothing,
               setting_widget_factory=_do_nothing):
    """Add a new plugin to Porcupine when it's starting.

    The name argument can be any string that does not conflict with
    other plugins. These are the valid keyword arguments to this
    function, and they all do nothing by default:

      start_callback(editor)
        This function will be called with a porcupine.editor.Editor
        object as its only argument when Porcupine starts.

      filetab_hook(filetab)
        This function is called when a new filetabs.FileTab is created.
        It should set up the filetab, and then optionally yield and undo
        everything it did. It will be called with a
        porcupine.filetabs.FileTab object as the only argument.

      setting_widget_factory(labelframe):
        This function is called when the setting dialog is opened for
        the first time. It should create other tkinter widgets for
        changing the settings into the given tkinter LabelFrame widget.
        The labelframe is displayed in the setting dialog only if this
        callback returns True.
    """
    plugin = types.SimpleNamespace(
        name=name,
        start_callback=start_callback,
        filetab_hook=filetab_hook,
        setting_widget_factory=setting_widget_factory,
    )
    plugins.append(plugin)


# these are wrapped tightly in try/except because someone might write
# Porcupine plugins using Porcupine, so Porcupine MUST be able to start
# if the plugins are broken

def load(editor):
    assert not plugins, "cannot load plugins twice"

    modulenames = []
    for path in __path__:    # this line looks odd
        for name, ext in map(os.path.splitext, os.listdir(path)):
            if name.isidentifier() and name[0] != '_' and ext == '.py':
                modulenames.append(__name__ + '.' + name)

    # plugins should be made so that their loading order doesn't matter,
    # so let's heavily discourage relying on it :D
    random.shuffle(modulenames)

    for name in modulenames:
        try:
            importlib.import_module(name)
        except Exception:
            log.exception("problem with importing %s", name)
        else:
            log.debug("successfully imported %s", name)

    log.info("found %d plugins", len(plugins))
    for plugin in plugins:
        try:
            plugin.start_callback(editor)
        except Exception as e:
            log.exception("the %r plugin's start_callback doesn't work",
                          plugin.name)


# the filetab stuff looks like a context manager at this point, but
# filetabs.py is actually simpler when these are kept apart like this

# TODO: would it be better to just expose some minimal callback based
# plugin API in filetabs.py and other places?

def init_filetab(filetab):
    state = []      # [(plugin, generator), ...]
    for plugin in plugins:
        try:
            generator = plugin.filetab_hook(filetab)
            if generator is None:
                # no yields
                continue
            next(generator)
            state.append((plugin.name, generator))

        except Exception:
            log.exception("the %r plugin's filetab_hook doesn't work",
                          plugin.name)

    filetab.__plugin_state = state


def destroy_filetab(filetab):
    for name, generator in filetab.__plugin_state:
        try:
            next(generator)
        except StopIteration:
            # it didn't yield, let's assume there's nothing to clean up
            pass
        except Exception:
            log.exception("the %r plugin's filetab_hook doesn't work", name)
