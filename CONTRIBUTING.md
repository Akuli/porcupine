## Developing Porcupine

If you want to do something to Porcupine, that's awesome!
I have tried to make contributing easy:
- Some issues are labeled as "good first issue".
- If you don't understand what I meant in an issue, please ask me to clarify it.
    I have written most issues so that I understand what I wrote,
    and if you are new to Porcupine, you likely need a longer explanation to understand what the problem is.
- Don't worry about asking too many questions!
    It's not annoying. I like interacting with other programmers.
- There is not much boilerplate involved in the contributing process.
    You just create a pull request and that's it.
    You can choose an issue and start working on it, without prior permission.
    Instead of working on an issue, you can also create something that you would
    like to have in an editor.
- You don't need to read anything before you can get started.
    I recommend having a look at [the Porcupine plugin API docs](https://akuli.github.io/porcupine/),
    but that's not required.
- Don't worry too much about whether your code is good or not.
    I will review the pull requests and try to help you out.
    There are also checks running on GitHub Actions.

To get started, make a fork of Porcupine with the button in the top right corner of this page.
Then install Python 3.7 or newer and [git](https://git-scm.com/), and run these commands:

    git clone https://github.com/YourUserName/porcupine
    cd porcupine
    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    python3 -m porcupine

This should run Porcupine. If you change some of Porcupine's
code in the `porcupine` directory and you run `python3 -m porcupine` again, your changes
should be visible right away.

Windows-specific notes:
- You need to use `py` instead of `python3` when creating the venv,
    and `env\Scripts\activate` instead of `source env/bin/activate` to activate it.
- If creating the venv fails with an error message like `Error: [Errno 13] Permission denied: ...\\python.exe`,
    try creating the venv into a different folder.
    It is created into whatever folder you are currently `cd`'d to
    (i.e. the folder that shows up on the command prompt before the `>`).

Porcupine uses `mypy`, which is a tool that type-checks the code without running it.
For small pull requests, you probably don't need to run it on your computer as GitHub Actions runs it on your pull request anyway.
You can run it locally like this:

    mypy porcupine

It often points out problems like forgetting to check whether something is `None`.

Porcupine also uses `black` and `isort` to format code,
and you should run them after making changes.
For example, if you changed something in `porcupine/plugins/pastebin.py`, you would do:

    black porcupine/plugins/pastebin.py
    isort porcupine/plugins/pastebin.py

You can also just run `black porcupine` and `isort porcupine` to format everything.

If you forget to run `mypy`, `black` or `isort`, it doesn't matter.
GitHub Actions will let us know before I merge your PR.

After doing some development and closing the terminal that you set up the
environment in, you can go back to the environment by `cd`'ing to the correct
place and running `source env/bin/activate` again. You can run `deactivate` to undo
the `source env/bin/activate`.

Other commands you may find useful:
- `python3 -m pytest` runs tests. You will see lots of weird stuff happening
  while testing, and that's expected.
    A good way to debug a test to see what is actually going on is to add traces.
    It pauses the test to show you the current state of the program.
    - Use `import pdb` and `pdb.set_trace()` to set the pause points in the test. You can
      set as many as you like, and it can conveniently be done on one line: `import pdb; pdb.set_trace()`.
    - When the test pauses, type `cont` in terminal to continue the test.
    - If you at any time need to interact with the program during the pause,
      type `interact` in terminal. Exit interactive mode with `ctrl + D`.
- To see a report of test coverage, add `--cov=porcupine` to the above pytest
  command and then run `coverage html`. Open `htmlcov/index.html` in your favorite
  browser to view it.
- `cd docs` followed by `python3 -m sphinx . build` creates HTML documentation.
  Open `docs/build/index.html` in your favorite browser to view it.


## Where to talk to us

GitHub issues and pull request comments are the best way to contact other Porcupine developers.
Many are also sometimes (very inconsistently) on
[the ##learnpython channel of the libera IRC server](https://kiwiirc.com/nextclient/irc.libera.chat/##learnpython),
with same nicknames as on GitHub, usually at about 7PM to 11PM UTC.


## Releasing Porcupine

These instructions are meant for Porcupine maintainers.
Other people shouldn't need them.

1. Update `CHANGELOG.md` based on Git logs (e.g. `git log --all --oneline --graph`).
    You should add a new section to the beginning with `Unreleased` instead of a version number.
    Don't split the text to multiple lines any more than is necessary,
    as that won't show up correctly on GitHub's releases page.
2. Make a pull request of your changelog edits. Review carefully:
    changing the changelog afterwards is difficult, as the text gets copied into the releases page.
3. Merge the pull request and pull the merge commit to your local `master` branch.
4. Run `python3 scripts/release.py` from the `master` branch.
    The script pushes a tag named e.g. `v2022.08.28`,
    which triggers the parts of `.github/workflows/release-builds.yml`
    that have `if: startsWith(github.ref, 'refs/tags/v')` in them.
    They build and deploy docs, copy the changelog to the releases page, and so on.
5. Update `porcupine.wiki` if you added new features that are likely not obvious to users.

If you want, you can also do a release from a branch named `bugfix-release` instead of `master`.
This is useful if you fixed a bug that made Porcupine unusable for someone,
but the new features on `master` aren't ready for releasing yet.
