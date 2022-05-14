import os
import shutil
import subprocess
import sys

import pytest

from porcupine.plugins import python_venv

creates_venvs = pytest.mark.xfail(
    sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") != "true",
    reason="running exes from temp folders fails on some windows systems",
)


# This test is slow, because making venvs is slow
@creates_venvs
def test_venv_setting(tmp_path):
    assert python_venv.get_venv(tmp_path) is None

    # auto-detect venv
    subprocess.run([sys.executable, "-m", "venv", "env2"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    # Never change venv implicitly as new venvs are created
    subprocess.run([sys.executable, "-m", "venv", "env1"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    subprocess.run([sys.executable, "-m", "venv", "env3"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    for env in ["env1", "env2", "env1", "env1", "env2", "env2"]:
        python_venv.set_venv(tmp_path, tmp_path / env)
        assert python_venv.get_venv(tmp_path) == tmp_path / env

    # Explicitly say no to using venvs, prevent auto-detection from running
    python_venv.set_venv(tmp_path, None)
    for lel in range(10):
        assert python_venv.get_venv(tmp_path) is None


@creates_venvs
def test_venv_becomes_invalid(tmp_path, caplog):
    subprocess.run([sys.executable, "-m", "venv", "env"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env"

    shutil.rmtree(tmp_path / "env")

    # Make sure it warns about the venv only once
    for lel in range(100):
        assert python_venv.get_venv(tmp_path) is None
    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith("Python venv is no longer valid")
