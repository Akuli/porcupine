import shutil
import subprocess
import sys
from functools import partial
from pathlib import Path

import pytest

from porcupine import get_tab_manager
from porcupine.plugins.git_status import run_git_status


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_added_and_modified_content(tree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    subprocess.check_call(["git", "init", "--quiet"], stdout=subprocess.DEVNULL)
    tree.add_project(tmp_path)

    Path("a").write_text("a")
    Path("b").write_text("b")
    subprocess.check_call(["git", "add", "a", "b"])
    Path("b").write_text("lol")
    [project_id] = tree.get_children()

    get_tab_manager().event_generate("<<FileSystemChanged>>")
    assert set(tree.item(project_id, "tags")) == {"git_modified"}

    subprocess.check_call(["git", "add", "a", "b"])
    get_tab_manager().event_generate("<<FileSystemChanged>>")
    assert set(tree.item(project_id, "tags")) == {"git_added"}


weird_filenames = [
    "foo bar.txt",
    "foo\tbar.txt",
    "foo\nbar.txt",
    "foo'bar.txt",
    "örkkimörkkiäinen.ö",
    "bigyó.txt",
    "2π.txt"]
if sys.platform != "win32":
    # Test each "Windows-forbidden" character: https://stackoverflow.com/a/31976060
    weird_filenames += [
    "foo<bar.txt",
    "foo>bar.txt",
    "foo:bar.txt",
    'foo"bar.txt',
    r"foo\bar.txt",
    r"foo\123.txt",  # not a special escape code, only looks like it
    "foo|bar.txt",
    "foo?bar.txt",
    "foo*bar.txt",
    ]


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
@pytest.mark.parametrize("filename", weird_filenames)
def test_funny_paths(tmp_path, filename):
    (tmp_path / filename).write_text("blah")
    subprocess.check_call(["git", "init", "--quiet"], cwd=tmp_path, stdout=subprocess.DEVNULL)
    subprocess.check_call(["git", "add", "."], cwd=tmp_path)

    statuses = run_git_status(tmp_path)
    assert statuses[tmp_path / filename] == "git_added"


@pytest.mark.skipif(shutil.which("git") is None, reason="git not found")
def test_merge_conflict(tree, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Resulting output of 'git log --graph --oneline --all':
    #
    #    * 84dca05 (HEAD -> b) b
    #    | * 9dbd837 (main) a
    #    |/
    #    * e16c2a7 initial
    run = partial(subprocess.run, stdout=subprocess.DEVNULL, shell=True, check=True)
    run("git init --quiet -b main")
    run("git config user.name foo")  # not --global, will stay inside repo
    run("git config user.email foo@bar.baz")
    Path("file").write_text("initial")
    run("git add file")
    run("git commit -m initial")
    Path("file").write_text("a")
    run("git add file")
    run("git commit -m a")
    run("git checkout --quiet -b b HEAD~")  # can't use HEAD^ because ^ is special in windows
    Path("file").write_text("b")
    run("git add file")
    run("git commit -m b")
    run("git merge main", check=False)  # Git returns status 1 when merge conflict occurs

    tree.add_project(tmp_path)
    [project_id] = tree.get_children()
    assert set(tree.item(project_id, "tags")) == {"git_mergeconflict"}
