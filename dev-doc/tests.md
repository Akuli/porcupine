# Tests

This file is about automated tests that ensure Porcupine is working correctly.
Instead of just "tests", you can call them "unit tests" or "integration tests"
depending on your personal opinions and views.


## When to write tests?

Many contributors don't need to care about tests at all.
GitHub Actions runs the tests for you when you make a pull request,
and often changes to Porcupine are so simple that they don't need tests.

Do not write tests for simple and commonly used things.
Porcupine maintainers (Akuli and rdbende) use Porcupine almost every day.
We will notice if saving a file doesn't work, for example.

Also, tests should be easier to understand than the code they are testing.
Seriously, how would a test help convince us that the code is correct,
if it's easier to just read the code?
This sounds obvious, but apparently it isn't obvious to some web developers.

That said, you should probably write tests when:
- The code is hard to get right (for example, there are many weird corner cases).
- It is easy to break the code in unintended ways when you try to modify it.
- The test is simple, easy to understand, and easy to get right when writing it initially.
- If the feature was broken, it might take a long time for Porcupine developers to notice it.
- If the feature was broken, it would break other things in surprising ways,
    and it would be difficult to understand what happened.

Last but not least, use your common sense.
The guidelines given here are not hard rules, and sometimes it makes sense to break them.


## Running Tests

Running all tests from terminal:

```
(env)$ python -m pytest
```

The tests launch a new instance of Porcupine that you will see on your screen as the tests run.
It will look crazy as the tests do stuff with it, and that's expected.

Here `-m pytest` tells Python to run the pytest module.
You need to run pytest using Python's `-m` switch.
If you just type `pytest`, it will fail to import porcupine.

If you are using Porcupine to develop Porcupine,
you can set up the F8 key (or F5, or F6, or F7) to run tests like this:
1. Open any of Porcupine's Python files.
2. Press Shift+F8.
3. Fill in the dialog that appears:
    - Run this command: `python3 -m pytest`
    - In this directory: `{project_path}`
    - Select "Display the output inside the Porcupine window"
3. Click "Run". The tests will run.
4. Press F8. The tests will run again.

Running all tests is slow, and often you want to run only some of them.
For example, let's say you changed how indentation works,
and you want to run all tests related to indentation.
You can do this:

```
(env)$ python3 -m pytest -k indent -v
```

Here `-k indent` finds all tests where the function name or file name contains `indent`.
It selects all tests of [tests/test_indent_dedent.py](../tests/test_indent_dedent.py)
because the file name mentions `indent`,
and a couple other tests such as `test_pasting_selected_indented_code`
in [tests/test_pastebin_plugin.py](../tests/test_pastebin_plugin.py).
The `-v` flag shows which tests get selected, and is not needed.


## Writing Tests

Tests must go to the `tests/` folder and **test function names must start with `test_`**.
This is how pytest finds them.

Porcupine uses [pytest fixtures](https://docs.pytest.org/en/latest/how-to/fixtures.html).
For example, saving a file might be tested like this:

```python
def test_saving_file(filetab, tmp_path):
    filetab.textwidget.insert("end", "hello world")
    filetab.save_as(tmp_path / "hello.txt")
    assert (tmp_path / "hello.txt").read_text() == "hello world\n"
```

(The `trailing_newline` plugin added a newline when the file was saved.)

Some fixtures are built in to pytest (such as `tmp_path`),
while others are Porcupine-specific and defined in [tests/conftest.py](../tests/conftest.py) (such as `filetab`).
The `tmp_path` fixture gives you a path to a newly created empty folder, and deletes the folder when your test is done.
The `filetab` fixture adds a new tab (specifically, `porcupine.tabs.FileTab`) to the Porcupine instance
before running your test, and closes the tab when your test is done.

It is fine to do hacky things in tests to achieve what you need.
For example, many tests use [pytest's `monkeypatch` fixture](https://docs.pytest.org/en/latest/how-to/monkeypatch.html)
and [pytest-mock](https://pypi.org/project/pytest-mock/).
Dynamic typing helps with this.

The tests are not type-checked.
Type-checking the tests for a **library** is a good thing,
because it means that type-checking will work for users of the library.
But Porcupine is an **application**, and you almost never `import porcupine` outside Porcupine itself.
If you still think that static typing would be better for Porcupine's tests,
please create an issue so that we can discuss this.


## Debugging Tips

If you put `breakpoint()` somewhere (in a test or in the actual code),
this will pause the test at that point and start a debugger session,
and you will see what is going on.
For example, you can type `next` to run the code one line at a time,
or `interact` to get an interactive `>>>` prompt that you can exit with *Ctrl+D*.
Type `cont` to exit the debugger and continue running the test.

On Windows, the UI tends to be frozen and inresponsive during debugger sessions.
Running `any_widget.update()` may help.
Here `any_widget` can be any tkinter widget, like the main window or a tab.

If you put `tkinter.mainloop()` somewhere, you can use the Porcupine instance as usual.
You can open and save files, click buttons, and so on.


## Global State

[Porcupine has global state](architecture-and-design.md#global-state).
For tests, this means that many things do not reset between tests.
Some things are cleaned up by fixtures defined in [conftest.py](../tests/conftest.py),
but not everything is.

For example, if your test creates new tabs,
[conftest.py](../tests/conftest.py) will close them before the next test runs.
But if your test adds something to the menubar at the top of the editor,
it will stay there until the end of the test session,
because there is no cleanup code for menu items.
This is fine, because having some extra items in the menubar is unlikely to
confuse other tests or Porcupine developers.
