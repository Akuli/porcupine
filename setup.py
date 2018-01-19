import sys
import tkinter
import os
import re

assert sys.version_info >= (3, 4), "Porcupine requires Python 3.4 or newer"
assert tkinter.TkVersion >= 8.5, "Porcupine requires Tk 8.5 or newer"


from setuptools import setup, find_packages  # noqa


def get_requirements():
    with open('requirements.txt', 'r') as file:
        for line in map(str.strip, file):
            if (not line.startswith('#')) and line:
                yield line


def find_metadata():
    with open(os.path.join('porcupine', '__init__.py')) as file:
        content = file.read()

    result = dict(re.findall(
        r'''^__(author|copyright|license)__ = ['"](.*)['"]$''',
        content, re.MULTILINE))
    assert result.keys() == {'author', 'copyright', 'license'}, result

    # version is defined like this: __version__ = '%d.%d.%d' % version_info
    version_info = re.search(r'^version_info = \((\d+), (\d+), (\d+)\)',
                             content, re.MULTILINE).groups()
    result['version'] = '%s.%s.%s' % version_info

    return result


setup(
    name='Porcupine',
    description="An editor that sucks less than IDLE",
    keywords='editor tkinter idle beginner suck',
    url='https://github.com/Akuli/porcupine',
    install_requires=list(get_requirements()),
    packages=find_packages(),
    package_data={
        '': ['*.txt', '*.gif', '*.sh', '*.ini'],
        # this is needed because porcupine/images isn't a package
        'porcupine': ['images/*'],
    },
    entry_points={
        'gui_scripts': ['porcu = porcupine.__main__:main'],
    },
    zip_safe=False,
    **find_metadata()       # must not end with , before python 3.5
)
