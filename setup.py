# flake8: noqa
import sys
assert sys.version_info >= (3, 3), "Porcupine requires Python 3.3 or newer"
import tkinter     # just to make sure it's there

from setuptools import setup, find_packages

import porcupine


setup(
    name='Porcupine',
    description="An editor that sucks less than IDLE",
    keywords='editor tkinter idle beginner suck',
    url='https://github.com/Akuli/porcupine',
    author=porcupine.__author__,
    version=porcupine.__version__,
    copyright=porcupine.__copyright__,
    license='MIT',
    # requests isn't really needed but most pastebins in
    # plugins/pastebin.py use it
    install_requires=['appdirs', 'requests', 'pygments>=1.6'],
    packages=find_packages(),
    package_data={
        '': ['*.txt', '*.gif', '*.sh', '*.ini'],
        # this is needed because porcupine/images isn't a package
        'porcupine': ['images/*'],
    },
    entry_points = {
        'gui_scripts': ['porcupine = porcupine.__main__:main'],
    },
    zip_safe=False,
)
