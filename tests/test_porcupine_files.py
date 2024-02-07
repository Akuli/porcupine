import datetime
from pathlib import Path

import tomli

import porcupine


def test_license_file():
    with (Path(__file__).absolute().parent.parent / "LICENSE").open() as file:
        copyright_line = file.readlines()[2]
    assert copyright_line.startswith("Copyright (c)")
    assert porcupine.__copyright__ == copyright_line.strip()


def test_copyright():
    assert str(datetime.datetime.now().year) in porcupine.__copyright__


# Porcupine dependencies are specified in pyproject.toml, but also kept in
# requirements-dev.txt for a convenient and familiar workflow. You just
# "pip install -r requirements-dev.txt" when you start developing Porcupine.
def test_requirements_and_pyproject_toml_in_sync():
    reqs_dev_content = []
    with open("requirements-dev.txt") as file:
        for line in file:
            requirement = line.split("#")[0].strip()
            if requirement:
                reqs_dev_content.append(requirement)

    with open("pyproject.toml", "rb") as file:
        toml_content = tomli.load(file)

    assert (
        toml_content["project"]["dependencies"]
        + toml_content["project"]["optional-dependencies"]["dev"]
        == reqs_dev_content
    )
