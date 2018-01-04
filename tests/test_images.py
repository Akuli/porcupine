import pytest

from porcupine import images


def test_get():
    with pytest.raises(FileNotFoundError):
        images.get('watwat')
