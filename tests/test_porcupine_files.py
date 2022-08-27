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


# The intended way to store dependency info is that setup.py or pyproject.toml contains version
# ranges, and requirements.txt contains specific versions in those ranges so that each deployment
# gets the same dependencies from there.
#
# A downside is that if your deployment also gets dependencies from other places, they could specify
# conflicting versions. This could be a problem for Porcupine: even though users usually install
# Porcupine into a virtualenv that doesn't contain anything else, I don't want to assume that they
# do.
#
# Another downside with pinning for Porcupine would be dependencies getting outdated easily.
#
# Solution: pin only the packages where updating will likely break things, and keep the same
# dependencies in requirements.txt (for easy "pip install -r requirements.txt" during development)
# and in pyproject.toml (for installing released versions).
def test_requirements_and_pyproject_toml_in_sync():
    requirements = []
    with open("requirements.txt", "r") as file:
        for line in file:
            requirement = line.split('#')[0].strip()
            if requirement:
                requirements.append(requirement)

    with open("pyproject.toml", "rb") as file:
        assert tomli.load(file)["project"]["dependencies"] == requirements
