import pathlib
import tempfile

from porcupine import tabs


def test_filetab_path_gets_resolved(tabmanager):
    with tempfile.TemporaryDirectory() as d:
        (pathlib.Path(d) / 'dir1').mkdir()
        (pathlib.Path(d) / 'dir2').mkdir()
        (pathlib.Path(d) / 'file1').touch()
        (pathlib.Path(d) / 'file2').touch()
        funny1 = pathlib.Path(d) / 'dir1' / '..' / 'file1'
        funny2 = pathlib.Path(d) / 'dir2' / '..' / 'file2'

        tab = tabs.FileTab(tabmanager, path=funny1)
        assert tab.path != funny1
        assert tab.path.samefile(funny1)
        assert '..' not in tab.path.parts

        tab.path = funny2
        assert tab.path != funny2
        assert tab.path.samefile(funny2)
        assert '..' not in tab.path.parts
