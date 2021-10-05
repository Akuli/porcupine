import shutil
import subprocess
import sys

from porcupine.plugins import python_venv


# This test is slow, because making venvs is slow
def test_venv_setting(tmp_path):
    assert python_venv.get_venv(tmp_path) is None

    subprocess.run([sys.executable, "-m", "venv", "env2"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    # Never change venv implicitly, as new venvs are created
    subprocess.run([sys.executable, "-m", "venv", "env1"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    subprocess.run([sys.executable, "-m", "venv", "env3"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env2"

    for env in ["env1", "env2", "env1", "env1", "env2", "env2"]:
        python_venv.set_venv(tmp_path, tmp_path / env)
        assert python_venv.get_venv(tmp_path) == tmp_path / env


def test_venv_becomes_invalid(tmp_path, caplog):
    subprocess.run([sys.executable, "-m", "venv", "env"], cwd=tmp_path, check=True)
    assert python_venv.get_venv(tmp_path) == tmp_path / "env"

    shutil.rmtree(tmp_path / "env")

    # Make sure it warns about the venv only once
    for lel in range(100):
        assert python_venv.get_venv(tmp_path) is None
    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith("Python venv is no longer valid")
