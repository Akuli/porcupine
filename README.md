# Porcupine

Porcupine is an editor written with the notorious Tkinter library. It supports
most things you would expect from an editor, such as autocompletions and syntax
highlighting.

![Screenshot.](screenshot.png)

Most important features:
- Syntax highlighting with [Pygments][] (supports many programming languages
  and color themes, extensible)
- Autocompletions
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

There are [more detailed instructions on Porcupine
Wiki](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine).

### Debian-based Linux distributions (e.g. Ubuntu, Mint)

Open a terminal and run these commands:

    sudo apt install python3-tk python3-pip
    python3 -m pip install --user --upgrade pip wheel
    python3 -m pip install https://github.com/Akuli/porcupine/archive/master.zip
    python3 -m porcupine &

### Other Linux distributions

Install Python 3.6 or newer with pip and tkinter somehow. Then run these
commands:

    python3 -m pip install --user --upgrade pip wheel
    python3 -m pip install https://github.com/Akuli/porcupine/archive/master.zip
    python3 -m porcupine &

### Mac OSX

I don't have a Mac. If you have a Mac, you can help me a lot by installing
Porcupine and letting me know how well it works.

I think you can download Python with tkinter from
[python.org](https://www.python.org/) and then run the commands for
"other Linux distributions" above.

### Windows

Install Python 3.6 or newer from [python.org](https://www.python.org/). Make sure that
the "Install launchers for all users" box gets checked and tkinter gets
installed. Then open PowerShell or command prompt, and run these commands:

    py -m pip install --user --upgrade pip wheel
    py -m pip install https://github.com/Akuli/porcupine/archive/master.zip
    pyw -m porcupine

### Development Install

See [below](#developing-porcupine).

## FAQ

### Help! Porcupine doesn't work.
Please [update Porcupine](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine#updating-porcupine).
If it still doesn't work, [let me know by creating an issue on
GitHub](http://github.com/Akuli/porcupine/issues/new).

### Why not use editor X?
Because Porcupine is better.

### I want an editor that does X, but X is not in the feature list above. Does Porcupine do X?
Maybe it can, see [the more_plugins directory](more_plugins/). If you don't
find what you are looking for you can write your own plugin, or alternatively,
you can [create an issue on GitHub](https://github.com/Akuli/porcupine/issues/new)
and hope that I feel like writing the plugin for you.

### Is Porcupine based on IDLE?
Of course not. IDLE is an awful mess that you should stay far away from.

### Why did you create a new editor?
Because I can.

### Why did you create a new editor in tkinter?
Because I can.

### How does feature X work?
See [porcupine/](porcupine/)X.py or [porcupine/plugins/](porcupine/plugins/)X.py.

### Does Porcupine support programming language X?
You will likely get syntax highlighting without any configuring
and autocompletions with a few lines of configuration file editing.
See [the instructions on Porcupine wiki](https://github.com/Akuli/porcupine/wiki/Getting-Porcupine-to-work-with-a-programming-language).

### Can I play tetris with Porcupine?
Of course, just install the tetris plugin. See [more_plugins](more_plugins/).

### Is Porcupine an Emacs?
Not by default, but you can [install more plugins](more_plugins/).


## Developing Porcupine

If you are interested in doing something to Porcupine yourself, that's awesome!
[The plugin API docs](https://akuli.github.io/porcupine/) will help you get
started. Even if you are not going to write Porcupine plugins or do anything
related to plugins, they will probably give you an idea of how things are done
in Porcupine.

If you want to develop porcupine, install Python 3.6 or newer and
[git](https://git-scm.com/), and run these commands:

    git clone https://github.com/Akuli/porcupine
    cd porcupine
    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    python3 -m porcupine

This should run Porcupine. If you change some of Porcupine's
code in the `porcupine` directory and you run `porcu` again, your changes
should be visible right away.

After doing some development and closing the terminal that you set up the
environment in, you can go back to the environment by `cd`'ing to the correct
place and running `source env/bin/activate` again. You can run `deactivate` to undo
the `source env/bin/activate`.

If you are using Windows, you need to use `py` instead of `python3` and
`env\Scripts\activate.bat` instead of `source env/bin/activate`.

Here is a list of the commands I use when developing Porcupine:
- Git commands. I'll assume that you know how to use Git and GitHub.
- Type checking with mypy:
    - `git submodule init`
    - `git submodule update`
    - `mypy --show-error-codes --custom-typeshed-dir=typeshed porcupine more_plugins`
- `python3 -m pytest` runs tests. You will see lots of weird stuff happening
  while testing, and that's expected.
- `coverage run --include="porcupine/*" -m pytest` followed by `coverage html`
  creates a report of test coverage. Open `htmlcov/index.html` in your favorite
  browser to view it. If you don't have anything else to do, you can write more
  tests and try to improve the coverage :D
- `cd docs` followed by `sphinx-build . build` creates HTML documentation.
  Open `docs/_build/index.html` in your favorite browser to view it.

I also use these commands, but **I don't recommend running these yourself.**
Instead, ask me to run them if you need to.
- `python3 release.py major_or_minor_or_patch` increments the version number and
  runs all the commands needed for doing a new Porcupine release. Run it from
  inside a virtualenv with master branch checked out in git. The argument
  works like this:
    - `major`: version goes `0.bla.bla --> 1.0.0` (porcupine becomes stable)
    - `minor`: version goes `0.71.4 --> 0.72.0` (backwards-incompatible changes)
    - `patch`: version goes `0.71.3 --> 0.71.4` (bug fixes without breaking compatibility)


## Building the Windows installer

It's possible to create a `porcupine-setup.exe` that installs Porcupine with a
nice setup wizard that Windows users are familiar with. This is not the
recommended way to install Porcupine yet because I don't know where I could
upload the installers yet so people could just click a link to download.

You need a Windows for creating the installer. You can use real computers, but
I like to use virtual machines because I can run a 32-bit *and* a 64-bit
virtual machine in a 64-bit operating system, and I don't need to have Windows
installed on a real computer.

Install VirtualBox and download [one of these things from
Microsoft](https://developer.microsoft.com/en-us/microsoft-edge/tools/vms/).
The `x86` things are 32-bit Windowses, and `x64`s are 64-bit. Usually I build a
32-bit installer and a 64-bit installer, so I need two virtual machines.

If you don't have a really fast internet, it takes a while to download a
virtual machine. Play tetris with the tetris plugin (see
[more_plugins](more_plugins/)) while you are waiting.

The virtual machine comes as a zip. You can use Python to extract it:

    cd Downloads       # or wherever the downloaded zip ended up
    python3 -m zipfile -e TheZipFile.zip .

It will take a while, but not long enough for a tetris :( You should end up
with a `.ova` file in your Downloads folder. Start VirtualBox and click
"Import Appliance..." in the "File" menu. Select the `.ova` file and click
"Next" a couple times. Play more tetris.

Start the virtual machine by double-clicking it at left. If you downloaded
Windows 10, be aware that it uses a **lot** of RAM, about 4GB on my system.
It's also quite slow, so you may need to play tetris while it starts up.

Install these programs in the virtual machine:
- Git: https://git-scm.com/
- Python: https://www.python.org/
- NSIS: http://nsis.sourceforge.net/Download

Clicking the biggest "Download" and "Next" buttons works most of the time, but
watch out for these things:
- You need Python 3.6 or newer.
- If you are creating a 64-bit Porcupine installer, be sure to get a 64-bit
  Python. At the time of writing this thing (August 2018), you need to first
  click "All releases" on the Python website, and then the newest Python, and
  finally scroll down and click either one of the "Windows x86-64 *something*
  installer" links.

Now you are ready to build the executable! Open a command prompt and run some
commands:

    git clone https://github.com/Akuli/porcupine
    cd porcupine
    py -m pip install pillow pynsist
    py build-exe-installer.py

Note that this does *not* work in a virtualenv. I don't feel like figuring out
why right now. Pip will probably complain about stuff not in PATH, but it's OK,
you don't need to do anything to fix the complaints.

Now you should have an exe that installs a Porcupine. The last command should
prints the filename at the end of its output, and it seems to be always
`build\nsis\Porcupine_X.Y.Z.exe` where `X.Y.Z` is the Porcupine version.


## Publishing a new version of Porcupine

Please ask me (Akuli) to do these things instead of doing them yourself.
- Bump version number: merge changes to master branch, then `python3 release.py patch`
  (see `--help` if you don't know what `patch` means here)
- Build and publish updated docs: `docs/publish.py`
- Update `porcupine.wiki` as needed
