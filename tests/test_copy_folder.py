import tempfile
from pathlib import Path
import pytest

from porcupine.plugins.filemanager import copy_folder, can_copy_folder, FilenameMode


@pytest.fixture(scope="function")
def setup_folder():
    tmp_dir = tempfile.TemporaryDirectory()
    src_dir = Path(tmp_dir.name) / 'source'
    src_dir.mkdir()
    (src_dir / 'file1.txt').touch()
    (src_dir / 'file2.txt').touch()
    (src_dir / 'subdir').mkdir()
    (src_dir / 'subdir' / 'file3.txt').touch()
    yield src_dir, tmp_dir
    tmp_dir.cleanup()


def mock_ask_file_name(parent: Path, suggested_name: str, mode: FilenameMode) -> Path:
    return parent / suggested_name


def test_copy_folder(monkeypatch, setup_folder):
    # mock the ask_file_name function to return the suggested name without user interaction
    monkeypatch.setattr("porcupine.plugins.filemanager.ask_file_name", mock_ask_file_name)

    # use the source folder created by the setup_folder fixture
    source_folder, _ = setup_folder

    # calls the copy_folder function
    copy_folder(source_folder)

    # check if the copied folder and files exist and have the same content
    copied_folder = source_folder.parent / f"{source_folder.name}_copy"
    assert copied_folder.exists()
    assert (copied_folder / "file1.txt").exists()
    assert (copied_folder / "file2.txt").exists()
    assert (copied_folder / "subdir").exists()
    assert (copied_folder / "subdir" / "file3.txt").exists()


def test_can_copy_folder(setup_folder):
    src_dir, tmp_dir = setup_folder
    assert can_copy_folder(src_dir)
    assert not can_copy_folder(src_dir / 'file1.txt')
    assert not can_copy_folder(src_dir / 'nonexistent')
