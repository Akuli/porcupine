# Porcupine

Porcupine is an editor written with the notorious Tkinter library. It supports
most things you would expect from an editor, such as autocompletions and syntax
highlighting.

![Screenshot.](screenshot.png)

Most important features:
- Syntax highlighting with [Pygments][] (supports many programming languages
  and color themes, extensible)
- Autocompletions when pressing tab
- Jump to definition with Ctrl+click
- [Langserver] support
- [Editorconfig][] support
- Compiling files inside the editor window
- Running files in a separate terminal or command prompt window
- Automatic indenting and trailing whitespace stripping when Enter is pressed
- Indent/dedent block with Tab and Shift+Tab
- Commenting/uncommenting multiple lines by selecting them and typing a #
- Highlighting matching parentheses
- Line numbers
- Line length marker
- Find/replace
- Code folding
- Multiple files can be opened at the same time like tabs in a web browser
- The tabs can be dragged out of the window to open a new Porcupine window conveniently

[Pygments]: https://pygments.org/
[Langserver]: https://langserver.org/
[Editorconfig]: https://editorconfig.org/

Porcupine also has [a very powerful plugin
API](https://akuli.github.io/porcupine/), and most of the above features are
implemented as plugins. This means that if you know how to use Python 3 and
tkinter, you can easily customize your editor to do anything you want to. In
fact, the plugin API is so powerful that if you run Porcupine without plugins,
it shows up as an empty window.

## Installing Porcupine

### Debian-based Linux distributions (e.g. Ubuntu, Mint)

Open a terminal and run these commands:

    sudo apt install python3-tk python3-pip
    sudo apt install --no-install-recommends tkdnd    # for drop_to_open plugin
    python3 -m pip install --user --upgrade pip wheel
    python3 -m pip install https://github.com/Akuli/porcupine/archive/v0.95.0.zip
    python3 -m porcupine

If you want to leave Porcupine running and use the same terminal for something else,
you can use `python3 -m porcupine &` instead of `python3 -m porcupine`.

### Other Linux distributions

Install Python 3.7 or newer with pip and tkinter somehow.
If you want drag and drop support, also install tkdnd for the Tcl interpreter that tkinter uses.
Then run these commands:

    python3 -m pip install --user --upgrade pip wheel
    python3 -m pip install https://github.com/Akuli/porcupine/archive/v0.95.0.zip
    python3 -m porcupine

If you want to leave Porcupine running and use the same terminal for something else,
you can use `python3 -m porcupine &` instead of `python3 -m porcupine`.

### Mac OSX

I don't have a Mac. If you have a Mac, you can help me a lot by installing
Porcupine and letting me know how well it works.

I think you can download Python with tkinter from
[python.org](https://www.python.org/) and then run the commands for
"other Linux distributions" above.

### Windows

Download a Porcupine installer from [the releases page](https://github.com/Akuli/porcupine/releases) and run it.
Because I haven't asked Microsoft to trust Porcupine installers,
you will likely get a warning similar to this one:

![Windows thinks it protected your PC](windows-defender.png)

You should still be able to run the installer by clicking "More info".
When installed, you will find Porcupine from the start menu.

### Development Install

See [below](#developing-porcupine).

## FAQ

### What's new in the latest Porcupine release?

See [CHANGELOG.md](CHANGELOG.md).

### Does Porcupine support programming language X?
You will likely get syntax highlighting without any configuring
and autocompletions with a few lines of configuration file editing.
See [the instructions on Porcupine wiki](https://github.com/Akuli/porcupine/wiki/Getting-Porcupine-to-work-with-a-programming-language).

### Help! Porcupine doesn't work.
Please [update Porcupine](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine#updating-porcupine).
If it still doesn't work, [let me know by creating an issue on
GitHub](http://github.com/Akuli/porcupine/issues/new).

### Is Porcupine written in Porcupine?

Yes. I wrote the very first version in `nano`, but Porcupine has changed a lot since.

### Why is it named Porcupine?

I think because I didn't find other projects named porcupine, but I don't remember exactly.
Originally, Porcupine was named "Akuli's Editor".

### I want an editor that does X, but X is not in the feature list above. Does Porcupine do X?
Maybe it can, see [the more_plugins directory](more_plugins/). If you don't
find what you are looking for you can write your own plugin, or alternatively,
you can [create an issue on GitHub](https://github.com/Akuli/porcupine/issues/new)
and hope that I feel like writing the plugin for you.

### Why did you create a new editor?
Because I can.

### Why did you create a new editor in tkinter?
Because I can.

### How does feature X work?
See [porcupine/](porcupine/)X.py or [porcupine/plugins/](porcupine/plugins/)X.py.

### Why not use editor X?
Because Porcupine is better.

### Is Porcupine based on IDLE?
Of course not. IDLE is an awful mess that you should stay far away from.

### Can I play tetris with Porcupine?
Of course, just install the tetris plugin. See [more_plugins](more_plugins/).


## Developing Porcupine

If you want to do something to Porcupine, that's awesome!
I have tried to make contributing easy:
- If you don't understand what I meant in an issue, please ask me to clarify it.
    I have written most issues so that I understand what I wrote,
    and if you are new to Porcupine, you likely need a longer explanation to understand what the problem is.
- Don't worry about asking too many questions!
    It's not annoying, and if you create several pull requests after I answer all your questions,
    I think answering the questions was definitely worth it.
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

You can talk with me on GitHub issues,
or chat at [##learnpython on libera](https://kiwiirc.com/nextclient/irc.libera.chat/##learnpython).
I am on ##learnpython at about 5PM to 9PM UTC.

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

After doing some development and closing the terminal that you set up the
environment in, you can go back to the environment by `cd`'ing to the correct
place and running `source env/bin/activate` again. You can run `deactivate` to undo
the `source env/bin/activate`.

If you are using Windows, you need to use `py` instead of `python3` and
`env\Scripts\activate.bat` instead of `source env/bin/activate`.

Here is a list of the commands I use when developing Porcupine:
- Git commands. I'll assume that you know how to use Git and GitHub.
- Type checking with mypy: `mypy porcupine more_plugins`
- `python3 -m pytest` runs tests. You will see lots of weird stuff happening
  while testing, and that's expected.
    A good way to debug a test to see what is actually going on is to add traces.
    It pauses the test to show you the current state of the program.
    - Use `import pdb` and `pdb.set_trace()` to set the pause points in the test. You can
      set as many as you like, and it can conveniently be done on one line: `import pdb; pdb.set_trace()`.
    - When the test pauses, type `cont` in terminal to continue the test.
    - If you at any time need to interact with the program during the pause,
      type `interact` in terminal. Exit interactive mode with `ctrl + D`.
- Code formatting tools: `black porcupine/` and `isort porcupine/`
- To see a report of test coverage, add `--cov=porcupine` to the above pytest
  command and then run `coverage html`. Open `htmlcov/index.html` in your favorite
  browser to view it. If you don't have anything else to do, you can write more
  tests and try to improve the coverage :D
- `cd docs` followed by `python3 -m sphinx . build` creates HTML documentation.
  Open `docs/build/index.html` in your favorite browser to view it.
- Linter commands run automatically on pull request or push. Usually I don't run
  them on my computer.

I also use these commands, but **I don't recommend running these yourself.**
Instead, ask me to run them if you need to.
- `python3 scripts/release.py major_or_minor_or_patch` increments the version number and
  runs all the commands needed for doing a new Porcupine release. Run it from
  inside a virtualenv with master branch checked out in git. The argument
  works like this:
    - `major`: version goes `0.bla.bla --> 1.0.0` (porcupine becomes stable)
    - `minor`: version goes `0.71.4 --> 0.72.0` (backwards-incompatible changes)
    - `patch`: version goes `0.71.3 --> 0.71.4` (bug fixes without breaking compatibility)

  Docs and Windows exe are built automatically after running the install script
  (see `.github/workflows/on-release.yml`), but `porcupine.wiki` may need manual updating.
