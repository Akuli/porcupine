import datetime
import pathlib

import porcupine


def test_license_file():
    with (pathlib.Path(__file__).absolute().parent.parent / 'LICENSE').open() as file:
        copyright_line = file.readlines()[2]
    assert copyright_line.startswith('Copyright (c)')
    assert porcupine.__copyright__ == copyright_line.strip()


def test_year():
    assert str(datetime.datetime.now().year) in porcupine.__copyright__
