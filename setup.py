from __future__ import annotations

import os
import platform
import re
import sys
import tkinter
from typing import Any, Iterator

from setuptools import find_packages, setup

assert sys.version_info >= (3, 7), "Porcupine requires Python 3.7 or newer"
assert tkinter.TkVersion >= 8.6, "Porcupine requires Tk 8.6 or newer"


# A hacky way to support conditions like:  python_version == "3.9" and sys_platform == "linux" and platform_machine == "x86_64"
# Ideally there would be a proper way to point pip at requirements.txt.
# Maybe just get rid of setup.py and requirements.txt, replace them with e.g. flit?
def evaluate_condition(condition: str) -> bool:
    condition = " ".join(condition.split())
    condition = condition.replace('"', "'")
    major, minor = sys.version_info[:2]
    condition = condition.replace(f"python_version == '{major}.{minor}'", "True")
    condition = condition.replace(f"sys_platform == '{sys.platform}'", "True")
    condition = condition.replace(f"platform_machine == '{platform.machine()}'", "True")
    return bool(re.fullmatch(r"True( and True)*", condition))


def get_requirements() -> Iterator[str]:
    with open("requirements.txt", "r") as file:
        for line in map(str.strip, file):
            if (not line.startswith("#")) and line:
                if ";" in line:
                    requirement, condition = line.split(";")
                    if evaluate_condition(condition):
                        yield requirement
                        continue
                else:
                    yield line


def find_metadata() -> dict[Any, Any]:
    with open(os.path.join("porcupine", "__init__.py")) as file:
        content = file.read()

    result = dict(
        re.findall(r"""^__(author|copyright|license)__ = ['"](.*)['"]$""", content, re.MULTILINE)
    )
    assert result.keys() == {"author", "copyright", "license"}, result

    # version is defined like this: __version__ = '%d.%d.%d' % version_info
    match = re.search(r"^version_info = \((\d+), (\d+), (\d+)\)", content, re.MULTILINE)
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
        "": ["*.txt", "*.gif", "*.sh", "*.toml", "*.tcl", "*.yml"],
        # this is needed because porcupine/images isn't a package
        "porcupine": ["images/*"],
    },
    entry_points={"gui_scripts": ["porcu = porcupine.__main__:main"]},
    zip_safe=False,
    **find_metadata(),
)
