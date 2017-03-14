"""Settings and themes for Porcupine."""

import configparser
import glob
import os


config = configparser.ConfigParser()
themes = configparser.ConfigParser()


def load():
    # TODO: a better way to find these paths (but not appdirs to keep
    # downloading Porcupine as noob-friendly as possible)
    _here = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(_here, 'default_configs')
    user_config = os.path.join(os.path.expanduser('~'), '.porcupine')

    os.makedirs(user_config, exist_ok=True)
    os.makedirs(os.path.join(user_config, 'themes'), exist_ok=True)

    config.read([
        os.path.join(default_config, 'settings.ini'),
        os.path.join(user_config, 'settings.ini'),
    ])
    for path in [default_config, user_config]:
        files = glob.glob(os.path.join(path, 'themes', '*.ini'))
        themes.read(files)
