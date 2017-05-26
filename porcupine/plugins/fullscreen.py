"""Simple fullscreen mode button."""

from porcupine import utils


def toggle_fullscreen():
    root = utils.get_root()
    new_value = (not root.attributes('-fullscreen'))
    root.attributes('-fullscreen', new_value)


def setup(editor):
    editor.add_action(toggle_fullscreen, "View/Full Screen", 'F11', '<F11>')
