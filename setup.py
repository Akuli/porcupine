from __future__ import annotations

import os
import re
import sys
import tkinter
from typing import Any, Iterator

from setuptools import find_packages, setup

assert sys.version_info >= (3, 7), "Porcupine requires Python 3.7 or newer"
assert tkinter.TkVersion >= 8.6, "Porcupine requires Tk 8.6 or newer"


def get_requirements() -> Iterator[str]:
    with open("requirements.txt", "r") as file:
        for line in map(str.strip, file):
            if (not line.startswith("#")) and line:
                yield line


def find_metadata() -> dict[Any, Any]:
    with open(os.path.join("porcupine", "__init__.py")) as file:
        content = file.read()

    result = dict(
        re.findall(r"""^__(author|copyright|license)__ = ['"](.*)['"]$""", content, re.MULTILINE)
    )
    assert result.keys() == {"author", "copyright", "license"}, result

    # version is defined like this: __version__ = '%d.%d.%d' % version_info
    match = re.search(
        r"^version_info = \((\d+), (\d+), (\d+)\)", content, re.MULTILINE
    )
    assert match is not None
    result["version"] = "%s.%s.%s" % tuple(match.groups())

    return result


setup(
    name="Porcupine",
    description="A decent editor written in tkinter",
    url="https://github.com/Akuli/porcupine",
    install_requires=list(get_requirements()),
    packages=find_packages(),
    package_data={
        "": ["*.txt", "*.gif", "*.sh", "*.toml", "*.tcl"],
        # this is needed because porcupine/images isn't a package
        "porcupine": ["images/*"],
    },
    entry_points={"gui_scripts": ["porcu = porcupine.__main__:main"]},
    zip_safe=False,
    **find_metadata(),
)
