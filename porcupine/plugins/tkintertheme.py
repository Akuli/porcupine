"""Make all Tk widgets look like Porcupine's theme."""

from porcupine import plugins, utils
from porcupine.settings import config, color_themes


def set_theme(name):
    color = color_themes[name]['background']
    utils.get_root().tk_setPalette(color)


def session_hook(editor):
    old_color = utils.get_root()['bg']
    with config.connect('Editing', 'color_theme', set_theme):
        yield
    utils.get_root().tk_setPalette(old_color)


plugins.add_plugin("Tk Theme", session_hook=session_hook)
