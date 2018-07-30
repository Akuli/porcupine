# Porcupine

Porcupine is a simple and beginner-friendly editor. If you ever used anything
like Notepad, Microsoft Word or LibreOffice Writer before, you will feel right
at home. All features of Porcupine should work great on Windows, Linux and Mac
OSX.

![Screenshot.](screenshot.png)

Here's a list of the most important features:

- Syntax highlighting with [Pygments][] (supports many programming languages
  and color themes, extensible)
- Some filetype specific settings
- Compiling files inside the editor window
- Running files in a separate terminal or command prompt window
- Autocompleting with tab
- Automatic indenting and trailing whitespace stripping when Enter is pressed
- Indent/dedent block with Tab and Shift+Tab
- Commenting/uncommenting multiple lines by selecting them and typing a #
- Line numbers
- Line length marker
- Find/replace
- Simple setting dialog
- Multiple files can be opened at the same time like tabs in a web browser
- The tabs can be dragged out of the window to open a new Porcupine window
  conveniently
- Status bar that shows current line and column numbers

[Pygments]: http://pygments.org/

Porcupine also has [a very powerful plugin
API](https://akuli.github.io/porcupine/), and most of the above features are
implemented as plugins. This means that if you know how to use Python 3 and
tkinter, you can easily customize your editor to do anything you want to. In
fact, the plugin API is so powerful that if you run Porcupine without plugins,
it shows up as an empty window!

## Installing Porcupine

There are [more detailed instructions on Porcupine
Wiki](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine).

### Debian-based Linux distributions (e.g. Ubuntu, Mint)

Open a terminal and run these commands:

    sudo apt install python3-tk python3-pip
    python3 -m pip install --user http://goo.gl/SnlfHw
    python3 -m porcupine &

### Other Linux distributions

Install Python 3.4 or newer with pip and tkinter somehow. Then run this
command:

    python3 -m pip install --user http://goo.gl/SnlfHw
    python3 -m porcupine &

### Mac OSX

I don't have a Mac. If you have a Mac, you can help me a lot by installing
Porcupine and letting me know how well it works.

I think you can download Python with tkinter from
[python.org](https://www.python.org/) and then run the commands for
"other Linux distributions" above.

### Windows

Install Python 3.4 from [python.org](https://www.python.org/). Make sure that
the "Install launchers for all users" box gets checked and tkinter gets
installed. Then open PowerShell or command prompt, and run these commands:

    py -m pip install --user http://goo.gl/SnlfHw
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

If you want to develop porcupine, install [git](https://git-scm.com/), and then
set up an environment for developing Porcupine like this:

    git clone https://github.com/Akuli/porcupine
    cd porcupine
    python3 -m venv env
    . env/bin/activate
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pip install --editable .

Now running `porcu` should start Porcupine. If you change some of Porcupine's
code in the `porcupine` directory and you run `porcu` again, your changes
should be visible right away.

If you are using Windows, you need to use `py` instead of `python3`. You also
need to do something else instead of `. env/bin/activate`, but I don't remember
what. Sorry :(

After doing some development and closing the terminal that you set up the
environment in, you can go back to the environment by `cd`'ing to the correct
place and running `. env/bin/activate` again. You can run `deactivate` to undo
the `. env/bin/activate`.

Here is a list of the commands I use when developing Porcupine:
- Git commands. I'll assume that you know how to use Git and GitHub.
- `python3 -m pytest` runs tests. You will see lots of weird stuff happening
  while testing, and that's expected.
- `coverage run --include="porcupine/*" -m pytest` followed by `coverage html`
  creates a report of test coverage. Open `htmlcov/index.html` in your favorite
  browser to view it. If you don't have anything else to do, you can write more
  tests and try to improve the coverage :D
- `cd docs` followed by `sphinx-build . _build` creates HTML documentation.
  Open `docs/_build/index.html` in your favorite browser to view it.

I also use these commands, but **I don't recommend running these yourself.**
Instead, ask me to run them if you need to.
- `python3 docs/publish.py` uploads the documentation to
  https://akuli.github.io/porcupine/ .
- `python3 bump.py major_or_minor_or_patch` increments the version number and
  invokes `git commit`. Be sure to `git push` and `git push --tags` after this.
