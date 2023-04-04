import pytest

from porcupine._state import restart
from porcupine._state import get_main_window


def test_restart():
    restart()
    #assert 'normal' == get_main_window()
    assert get_main_window()
