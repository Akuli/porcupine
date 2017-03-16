"""Settings and color themes for Porcupine."""

import configparser
import glob
import os


config = configparser.ConfigParser()
color_themes = configparser.ConfigParser(default_section='Default')
_here = os.path.dirname(os.path.abspath(__file__))
_datadir = os.path.join(_here, 'data')
_user_config_dir = os.path.join(os.path.expanduser('~'), '.porcupine')


def load():
    # TODO: a better way to find these paths (but not appdirs to keep
    # downloading Porcupine as noob-friendly as possible)
    os.makedirs(os.path.join(_user_config_dir, 'themes'), exist_ok=True)

    config.read([
        os.path.join(_datadir, 'default_settings.ini'),
        os.path.join(_user_config_dir, 'settings.ini'),
    ])
    color_themes.read(
        [os.path.join(_datadir, 'default_themes.ini')]
        + glob.glob(os.path.join(_user_config_dir, 'themes', '*.ini'))
    )


_COMMENTS = """\
# This is a Porcupine configuration file. You can edit this manually,
# but any comments or formatting will be lost.
"""


def save():
    with open(os.path.join(_user_config_dir, 'settings.ini'), 'w') as f:
        print(_COMMENTS, file=f)
        config.write(f)
